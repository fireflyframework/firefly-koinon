# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual PostgreSQL locks, guards and independent application-process fences."""

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy.engine import make_url
from test_bulk_native import bulk as bulk
from test_bulk_native import request
from test_bulk_writer_leases import expire_writer

from koinon.knowledge.bulk.repositories import BulkRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def bulk_url():
    value = os.environ.get("KOINON_TEST_BULK_POSTGRES_URL")
    if not value:
        pytest.skip("Requires an explicitly owned isolated PostgreSQL Unix-socket fixture")
    url = make_url(value)
    directory = Path(url.query.get("host", ""))
    assert str(directory).startswith("/tmp/koinon-bulk-pg-")
    assert directory.is_dir() and directory.stat().st_mode & 0o077 == 0
    import psycopg
    from psycopg import sql

    name = "bulk_" + uuid4().hex
    with psycopg.connect(
        dbname=url.database,
        user=url.username,
        host=str(directory),
        port=int(url.query["port"]),
        autocommit=True,
    ) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    return url.set(database=name).render_as_string(hide_password=False)


@pytest.fixture(autouse=True)
async def guarded_database(bulk):
    engine = bulk.context.get_bean(DataSourceRegistry).get("primary").engine
    root = Path(__file__).resolve().parents[4]
    migrations = root / "deploy/migrations/native_versions"
    async with engine.begin() as connection:

        def install(sync):
            for path, method in (
                (migrations / "0024_bulk_intake.py", "_postgres_guards"),
                (next(migrations.glob("*_bulk_staging.py")), "install_guards"),
            ):
                spec = importlib.util.spec_from_file_location("owned_guards", path)
                migration = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(migration)
                with Operations.context(MigrationContext.configure(sync)):
                    getattr(migration, method)()

        await connection.run_sync(install)


async def child(tmp_path, values):
    path = tmp_path / (uuid4().hex + ".json")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(values, stream)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).parent) + os.pathsep + environment.get("PYTHONPATH", "")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("bulk_process_fixture.py")),
        str(path),
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    assert process.returncode == values.get("expected_exit", 0), stderr.decode()[-2500:]
    return json.loads(stdout.decode().splitlines()[-1])


async def test_two_native_processes_fence_expired_writer_and_publish_only_recovery(bulk, bulk_url, tmp_path):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await expire_writer(bulk, writer.upload_id)
    common = {
        "url": bulk_url,
        "root": bulk.service.settings.storage_root,
        "batch": batch.id,
        "item": item.id,
        "revision": batch.revision,
    }
    finished, recovered = await asyncio.gather(
        child(
            tmp_path,
            {
                **common,
                "operation": "finish",
                "ticket": {key: value for key, value in vars(writer).items() if key != "local_permit"},
            },
        ),
        child(tmp_path, {**common, "operation": "recover", "key": "recover"}),
    )
    assert finished == {"code": "BULK_UPLOAD_LEASE_LOST"}
    assert recovered["code"] == "ok"
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.item(batch.id, item.id)).winning_upload_id == writer.upload_id
        assert (await records.quota("global:uploads")).active_uploads == 0
        assert (await records.quota("global:recoveries")).active_uploads == 0
        assert (await records.quota("tenant:north")).reserved_bytes == 8


async def test_killed_verifier_process_resumes_existing_recovery_without_new_writer(bulk, bulk_url, tmp_path):
    from datetime import UTC, datetime

    from sqlalchemy import update

    from koinon.knowledge.bulk.entities import BulkRecovery, BulkUploadState

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await expire_writer(bulk, writer.upload_id)
    common = {
        "url": bulk_url,
        "root": bulk.service.settings.storage_root,
        "batch": batch.id,
        "item": item.id,
        "revision": batch.revision,
        "key": "recover",
    }
    crashed = await child(tmp_path, {**common, "operation": "claim-and-crash", "expected_exit": 17})
    assert crashed == {"code": "crashed-after-committed-fence"}
    registry = bulk.context.get_bean(DataSourceRegistry)
    async with registry.get("primary").engine.begin() as connection:
        for entity in (BulkRecovery, BulkUploadState):
            await connection.execute(update(entity).values(lease_until=datetime(2000, 1, 1, tzinfo=UTC)))
    resumed = await child(tmp_path, {**common, "operation": "recover"})
    assert resumed["code"] == "ok"
    async with infrastructure_unit(registry.get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert await records.upload_count(item.id) == 1
        assert (await records.item(batch.id, item.id)).winning_upload_id == writer.upload_id
        assert (await records.quota("global:recoveries")).active_uploads == 0


async def test_two_recovery_processes_cannot_double_release_or_duplicate_an_action(bulk, bulk_url, tmp_path):
    from sqlalchemy import func, select

    from koinon.knowledge.bulk.entities import BulkRecovery

    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    writer = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    await bulk.service.storage.put(writer.object_key, b"original", writer.sha256)
    await expire_writer(bulk, writer.upload_id)
    values = {
        "url": bulk_url,
        "root": bulk.service.settings.storage_root,
        "batch": batch.id,
        "item": item.id,
        "revision": batch.revision,
        "key": "recover",
        "operation": "recover",
    }
    results = await asyncio.gather(child(tmp_path, values), child(tmp_path, values))
    assert any(result["code"] == "ok" for result in results)
    assert {result["code"] for result in results} <= {"ok", "BULK_UPLOAD_ACTIVE"}
    engine = bulk.context.get_bean(DataSourceRegistry).get("primary").engine
    async with engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(BulkRecovery)) == 1
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        assert (await records.quota("global:uploads")).active_uploads == 0
        assert (await records.quota("global:recoveries")).active_uploads == 0


async def test_postgres_revocation_during_verification_cannot_publish(bulk):
    from test_bulk_writer_leases import (
        test_recovery_cannot_publish_after_authority_revocation_during_verification as check_revocation,
    )

    await check_revocation(bulk)


async def test_postgres_new_admission_reaps_only_expired_logical_owner(bulk):
    from test_bulk_writer_leases import (
        test_new_admission_fences_expired_logical_permit_without_replaying_original as check_expiry,
    )

    await check_expiry(bulk)


async def test_blob_original_survives_independent_process_without_any_shared_staging_directory(
    bulk, bulk_url, tmp_path
):
    import stat

    from azure.storage.blob import BlobServiceClient

    value = os.environ.get("KOINON_TEST_BULK_AZURITE_JSON")
    if not value:
        pytest.skip("Requires explicitly owned loopback-only Blob emulator")
    path = Path(value)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    emulator = json.loads(path.read_text())
    assert emulator["endpoint"].startswith("http://127.0.0.1:")
    container = "bulk-" + uuid4().hex
    with BlobServiceClient.from_connection_string(emulator["connection_string"]) as client:
        assert client.url.rstrip("/") == emulator["endpoint"].rstrip("/")
        client.create_container(container)
    settings = bulk.service.settings
    settings.storage_root = None
    settings.storage_backend = "azure"
    settings.azure_account_url = emulator["endpoint"]
    settings.azure_container = container
    settings.azure_prefix = "staging"
    bulk.service.storage.configured().native.connection_string = emulator["connection_string"]
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    receipt = await bulk.service.stage("issuer|editor", "north", batch.id, item.id, b"original", "upload")
    result = await child(
        tmp_path,
        {
            "url": bulk_url,
            "root": None,
            "batch": batch.id,
            "item": item.id,
            "operation": "read-original",
            "cloud": {
                "storage_backend": "azure",
                "azure_account_url": emulator["endpoint"],
                "azure_container": container,
                "azure_prefix": "staging",
            },
            "emulator_connection": emulator["connection_string"],
        },
    )
    assert result == {"code": "ok", "receipt": receipt.receipt_id, "sha256": receipt.sha256}
    assert not any((tmp_path / "private").rglob("*.blob"))

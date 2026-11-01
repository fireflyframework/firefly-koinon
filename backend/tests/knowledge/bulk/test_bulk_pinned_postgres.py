# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pinned original receipts through the actual migrated PostgreSQL bulk lifecycle."""

import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from psycopg import sql
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from test_bulk_native import bulk as bulk
from test_bulk_native import request
from test_bulk_pinned_migration import invalid_references
from test_bulk_writer_leases import expire_writer

from koinon.knowledge.bulk.dtos import BulkAction
from koinon.knowledge.bulk.repositories import BulkRepository

pytestmark = pytest.mark.integration


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bulk_url(request):
    uri = os.environ.get("KOINON_TEST_BULK_POSTGRES_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    socket = Path(url.query.get("host", ""))
    assert (url.host == "127.0.0.1" and url.port != 18783) or (
        str(socket).startswith("/tmp/koinon-bulk-pg-")
        and socket.is_dir()
        and socket.stat().st_mode & 0o077 == 0
    )
    plain = url.set(drivername="postgresql").render_as_string(hide_password=False)
    database = "pinned_bulk_" + uuid4().hex
    with psycopg.connect(plain, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    url = url.set(database=database)
    root = Path(__file__).resolve().parents[4]
    migrate = load(root / "deploy/migrate.py", "pinned_bulk_migrate")
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            config = migrate.history_config("native", root / "deploy/migrations/native_versions", connection)
            command.upgrade(config, getattr(request, "param", "heads"))
            connection.commit()
    finally:
        engine.dispose()
    return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


async def original(bulk, tmp_path, content=b"original"):
    batch = await bulk.service.create("issuer|editor", "north", request(bulk.target, content), "create")
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    ticket = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    path = tmp_path / "original"
    path.write_bytes(content)
    return batch, item, ticket, path


async def saved(bulk, ticket):
    registry = bulk.context.get_bean(DataSourceRegistry)
    async with infrastructure_unit(registry.get("primary")):
        records = bulk.context.get_bean(BulkRepository)
        upload = await records.upload_by_id(ticket.upload_id)
        assert upload.object_reference_json["sha256"] == ticket.sha256
        assert upload.status == "verified" and not upload.permit_held
        assert (await records.quota("global:uploads")).active_uploads == 0
        assert (await records.quota("tenant:north")).reserved_bytes == ticket.size_bytes
        return dict(upload.object_reference_json)


async def test_migrated_postgres_finishes_pinned_file_and_replays_exact_receipt(bulk, tmp_path):
    batch, item, ticket, path = await original(bulk, tmp_path)
    receipt = await bulk.service.finish_stream(
        "issuer|editor", "north", batch.id, item.id, ticket, path, 8, ticket.sha256
    )
    reference = await saved(bulk, ticket)
    replay = await bulk.service.reserve_stream("issuer|editor", "north", batch.id, item.id, "upload")
    again = await bulk.service.finish_stream(
        "issuer|editor", "north", batch.id, item.id, replay, None, 8, ticket.sha256
    )
    assert again == receipt and await saved(bulk, ticket) == reference
    assert (await bulk.service.get("issuer|editor", "north", batch.id)).counts == {"staged": 1}


async def test_migrated_postgres_recovers_retained_pinned_file_without_another_upload(bulk, tmp_path):
    batch, item, ticket, path = await original(bulk, tmp_path, b"x" * (32 * 1024**2 + 1))
    reference = await bulk.service.storage.put_file(ticket.object_key, path, ticket.sha256)
    await expire_writer(bulk, ticket.upload_id)
    await bulk.service.abort_stream("north", ticket)
    current = await bulk.service.recover_original(
        "issuer|editor",
        "north",
        batch.id,
        item.id,
        BulkAction(expected_revision=batch.revision),
        "recover",
    )
    assert current.counts == {"staged": 1}
    assert await saved(bulk, ticket) == reference.to_dict()
    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).get("primary")):
        assert await bulk.context.get_bean(BulkRepository).upload_count(item.id) == 1


async def test_migrated_postgres_pinned_reference_cannot_change_or_disappear(bulk, tmp_path, bulk_url):
    batch, item, ticket, path = await original(bulk, tmp_path)
    await bulk.service.finish_stream(
        "issuer|editor", "north", batch.id, item.id, ticket, path, 8, ticket.sha256
    )
    reference = await saved(bulk, ticket)
    uri = make_url(bulk_url).set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            "UPDATE koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
            (json.dumps(dict(reversed(list(reference.items())))), ticket.upload_id),
        )
        for field, value in [
            ("version", "another"),
            ("sha256", "f" * 64),
            ("key", "another"),
            ("size_bytes", 8.0),
            ("schema_version", 1.0),
        ]:
            with pytest.raises(psycopg.Error, match="Immutable bulk"):
                connection.execute(
                    "UPDATE koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
                    (json.dumps({**reference, field: value}), ticket.upload_id),
                )
        for value in (None, "null"):
            with pytest.raises(psycopg.Error, match="Immutable bulk"):
                connection.execute(
                    "UPDATE koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
                    (value, ticket.upload_id),
                )
        for assignment in ("object_key='other'", "permit_held=true", "status='uploading'"):
            with pytest.raises(psycopg.Error, match="Immutable bulk"):
                connection.execute(
                    "UPDATE koinon_bulk_uploads SET " + assignment + " WHERE id=%s", (ticket.upload_id,)
                )
        with pytest.raises(psycopg.Error, match="Retain bulk"):
            connection.execute("DELETE FROM koinon_bulk_uploads WHERE id=%s", (ticket.upload_id,))
    assert await saved(bulk, ticket) == reference


async def test_migrated_postgres_validates_first_pin_against_public_manifest_as_runtime(
    bulk, tmp_path, bulk_url
):
    _, item, ticket, path = await original(bulk, tmp_path)
    reference = (await bulk.service.storage.put_file(ticket.object_key, path, ticket.sha256)).to_dict()
    uri = make_url(bulk_url).set(drivername="postgresql").render_as_string(hide_password=False)
    role = "pinned_runtime_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(role))
        )
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        connection.execute(
            sql.SQL("GRANT SELECT ON public.koinon_bulk_items TO {}").format(sql.Identifier(role))
        )
        connection.execute(
            sql.SQL("GRANT SELECT,INSERT,UPDATE ON public.koinon_bulk_uploads TO {}").format(
                sql.Identifier(role)
            )
        )
        function = connection.execute(
            "SELECT prosecdef,proconfig FROM pg_proc "
            "WHERE oid='public.koinon_bulk_uploads_guard()'::regprocedure"
        ).fetchone()
        assert function == (False, ["search_path=pg_catalog"])
        connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
        connection.execute("CREATE TEMP TABLE koinon_bulk_items(id TEXT,sha256 TEXT,size_bytes BIGINT)")
        connection.execute("INSERT INTO pg_temp.koinon_bulk_items VALUES (%s,%s,9)", (item.id, "c" * 64))
        connection.execute("SET search_path=pg_temp,public")
        with pytest.raises(psycopg.Error, match="Invalid bulk pinned receipt"):
            connection.execute(
                "UPDATE public.koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
                (json.dumps({**reference, "sha256": "c" * 64, "size_bytes": 9}), ticket.upload_id),
            )
        for raw in (
            json.dumps(reference).replace('"size_bytes": 8', '"size_bytes": 8e0'),
            json.dumps(reference).replace('"schema_version": 1', '"schema_version": 1e0'),
        ):
            with pytest.raises(psycopg.Error, match="Invalid bulk pinned receipt"):
                connection.execute(
                    "UPDATE public.koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
                    (raw, ticket.upload_id),
                )
        for invalid in invalid_references(reference):
            with pytest.raises(psycopg.Error, match="Invalid bulk pinned receipt"):
                connection.execute(
                    "UPDATE public.koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
                    (json.dumps(invalid), ticket.upload_id),
                )
        connection.execute(
            "UPDATE public.koinon_bulk_uploads SET object_reference_json='null' WHERE id=%s",
            (ticket.upload_id,),
        )
        connection.execute(
            "UPDATE public.koinon_bulk_uploads SET object_reference_json=%s WHERE id=%s",
            (json.dumps(reference), ticket.upload_id),
        )
        with pytest.raises(psycopg.Error, match="Immutable bulk pinned receipt"):
            connection.execute(
                "UPDATE public.koinon_bulk_uploads SET object_reference_json=NULL WHERE id=%s",
                (ticket.upload_id,),
            )
        with pytest.raises(psycopg.Error, match="Invalid bulk pinned receipt"):
            connection.execute(
                "INSERT INTO public.koinon_bulk_uploads "
                "(id,item_id,key_hash,object_key,status,permit_held,created_at,object_reference_json) "
                "VALUES ('forged',%s,'forged','unmatched','verified',false,CURRENT_TIMESTAMP,%s)",
                (item.id, json.dumps(reference)),
            )


@pytest.mark.parametrize("bulk_url", ["koinon_0039_answer_release"], indirect=True)
async def test_upgrade_retains_failed_original_then_explicit_recovery_pins_once(bulk, tmp_path, bulk_url):
    batch, item, ticket, path = await original(bulk, tmp_path, b"x" * (32 * 1024**2 + 1))
    with pytest.raises(DBAPIError, match="Immutable bulk identity or receipt"):
        await bulk.service.finish_stream(
            "issuer|editor", "north", batch.id, item.id, ticket, path, ticket.size_bytes, ticket.sha256
        )
    uri = make_url(bulk_url).set(drivername="postgresql+psycopg")
    engine = create_engine(uri)
    root = Path(__file__).resolve().parents[4]
    migrate = load(root / "deploy/migrate.py", "pinned_upgrade_migrate")
    try:
        with engine.connect() as connection:
            before = connection.exec_driver_sql("SELECT to_jsonb(u) FROM public.koinon_bulk_uploads u").all()
            config = migrate.history_config("native", root / "deploy/migrations/native_versions", connection)
            command.upgrade(config, "heads")
            connection.commit()
            assert (
                connection.exec_driver_sql("SELECT to_jsonb(u) FROM public.koinon_bulk_uploads u").all()
                == before
            )
    finally:
        engine.dispose()
    current = await bulk.service.recover_original(
        "issuer|editor",
        "north",
        batch.id,
        item.id,
        BulkAction(expected_revision=batch.revision),
        "recover-original",
    )
    assert current.counts == {"staged": 1}
    assert (await saved(bulk, ticket))["sha256"] == ticket.sha256

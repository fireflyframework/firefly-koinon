# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained import markers require exact immutable receipts under current source state."""

from dataclasses import replace
from types import SimpleNamespace

import psycopg
import pytest
from psycopg.types.json import Json
from test_source_concurrency_postgres import TENANT
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import accept_policy, attempt

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_dtos import LocalSourcePin
from koinon.integrations.content_sources.read_repository import SourceReadRepository

pytestmark = pytest.mark.integration
PIN = LocalSourcePin("asset", "canon", "native-space", "native-source", "native-version", "extraction")


@pytest.fixture
async def retained_origin(source_sessions, source_database):
    sessions, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        for table in (
            "lattice_domain_bindings",
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
        connection.execute(
            "INSERT INTO lattice_domain_bindings(id,tenant_id,catalog_id,workspace_id,domain,"
            "entity_kind,native_id,native_workspace_id,details_json,created_by,created_at) "
            "VALUES('binding','retained','asset','workspace','canon','document','native-source',"
            "'native-space','{}','issuer|alice',now())"
        )
        attempt(connection)
        connection.execute(
            "INSERT INTO koinon_content_imported_assets VALUES('asset','retained','source','attempt',now())"
        )
        from koinon.integrations.content_sources.read_authority import source_authority

        connection.execute(
            "UPDATE koinon_content_connections SET config_fingerprint=%s,scopes=%s",
            ("f" * 64, Json(["openid", "drive.readonly"])),
        )
        connection.execute("UPDATE koinon_content_mappings SET config_fingerprint=%s", ("f" * 64,))
        authority, authority_digest = source_authority(
            SimpleNamespace(
                id="connection",
                tenant_id=TENANT,
                owner="issuer|alice",
                provider="google_drive",
                external_subject="provider-alice",
                external_tenant=None,
                issuer="https://accounts.google.com",
                config_fingerprint="f" * 64,
                scopes=["openid", "drive.readonly"],
            )
        )
        connection.execute(
            "INSERT INTO koinon_content_policies(id,tenant_id,owner,mapping_id,revision,mapping_revision,"
            "authority_sha256,policy_json,policy_sha256,root_ancestry_json,review_id,review_digest,"
            "review_expires_at,accepted_by,accepted_session_hash,accepted_operation_id,"
            "accepted_at,created_at) "
            "VALUES('policy','retained','issuer|alice','mapping',1,1,%s,%s,%s,'[\"root\"]','review',%s,"
            "now()+interval '1 day',NULL,NULL,NULL,NULL,now())",
            (authority_digest, Json({"authority": authority}), "b" * 64, "c" * 64),
        )
        accept_policy(connection)
        connection.execute(
            "INSERT INTO koinon_content_sync_states VALUES"
            "('mapping','retained','policy',false,1,NULL,NULL,0,0,now())"
        )
        for table in (
            "koinon_content_policies",
            "koinon_content_sync_states",
            "koinon_content_folder_publications",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
    return sessions, uri


async def test_marker_without_committed_exact_receipt_denies_even_retained_read(retained_origin):
    sessions, _ = retained_origin
    async with sessions() as session:
        with pytest.raises(SourceError, match="unavailable"):
            await SourceReadRepository(session=session).resolve(TENANT, (PIN,))


def commit_origin(uri):
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt'",
            (
                Json(
                    {
                        "domain": "canon",
                        "native_workspace_id": "native-space",
                        "native_source_id": "native-source",
                        "native_asset_id": "native-source",
                        "source_version_id": "native-version",
                        "extraction_id": "extraction",
                        "sha256": "d" * 64,
                        "size_bytes": 7,
                    }
                ),
            ),
        )
        connection.execute(
            "INSERT INTO koinon_content_imported_versions VALUES('attempt','retained','source','asset',"
            "'canon','native-space','native-source','native-source','native-version','extraction',now())"
        )


async def test_exact_origin_rejects_other_version_tenant_and_disconnected_importer(retained_origin):
    sessions, uri = retained_origin
    commit_origin(uri)
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        origin = (await reader.resolve(TENANT, (PIN,)))[0]
        assert origin.target.item_id == "remote-file" and origin.target.version == "v1"
        with pytest.raises(SourceError, match="unavailable"):
            await reader.resolve(TENANT, (replace(PIN, version_id="other"),))
        with pytest.raises(SourceError, match="access_denied"):
            await reader.resolve("other-tenant", (PIN,))
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_content_connections SET revision=2,secret_ciphertext=%s WHERE id='connection'",
            (b"rotated-credential",),
        )
    async with sessions() as session:
        assert (await SourceReadRepository(session=session).resolve(TENANT, (PIN,)))[0].target.version == "v1"
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_content_connections SET scopes=%s,revision=3 WHERE id='connection'",
            (Json(["openid"]),),
        )
    async with sessions() as session:
        with pytest.raises(SourceError, match="authority_changed"):
            await SourceReadRepository(session=session).resolve(TENANT, (PIN,))
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_content_connections SET scopes=%s WHERE id='connection'",
            (Json(["openid", "drive.readonly"]),),
        )
        connection.execute(
            "UPDATE koinon_content_connections SET status='disconnected',revision=4,secret_ciphertext=NULL"
            " WHERE id='connection'"
        )
    async with sessions() as session:
        with pytest.raises(SourceError, match="unavailable"):
            await SourceReadRepository(session=session).resolve(TENANT, (PIN,))


async def test_restore_preflight_exempts_only_target_and_still_checks_current_origin(
    retained_origin, monkeypatch
):
    from contextlib import asynccontextmanager

    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.read_authority import SourceReadAuthority

    sessions, uri = retained_origin
    commit_origin(uri)
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET status='archived' WHERE id='asset'")

    @asynccontextmanager
    async def unit(**kwargs):
        yield

    monkeypatch.setattr("koinon.integrations.content_sources.read_authority.primary_authority", unit)
    async with sessions() as session:

        class Catalog:
            async def _refresh_managed_memberships(self, actor):
                pass

            async def get_identity(self, actor, tenant, identifier):
                value = (
                    await session.execute(
                        select(CatalogEntry.id, CatalogEntry.parent_id, CatalogEntry.status).where(
                            CatalogEntry.tenant_id == tenant, CatalogEntry.id == identifier
                        )
                    )
                ).one()
                return value

        authority = SourceReadAuthority(SourceReadRepository(session=session), None, Catalog())
        assert len(await authority._snapshot("issuer|alice", TENANT, (PIN,), archived_target="asset")) == 1
        with pytest.raises(SourceError, match="access_denied"):
            await authority._snapshot("issuer|alice", TENANT, (PIN,))
        await session.rollback()
        with psycopg.connect(uri) as connection:
            connection.execute("UPDATE lattice_catalog SET status='archived' WHERE id='folder'")
        with pytest.raises(SourceError, match="access_denied"):
            await authority._snapshot("issuer|alice", TENANT, (PIN,), archived_target="asset")
        await session.rollback()
        with psycopg.connect(uri) as connection:
            connection.execute("UPDATE lattice_catalog SET status='ready' WHERE id='folder'")
            connection.execute("UPDATE koinon_content_objects SET remote_version='v2' WHERE id='origin'")
        with pytest.raises(SourceError, match="version_changed"):
            await authority._snapshot("issuer|alice", TENANT, (PIN,), archived_target="asset")

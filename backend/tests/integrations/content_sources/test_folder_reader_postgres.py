# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Folder publication origins constrain reader projections before payload hydration."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Json
from sqlalchemy import select
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_folder_publication_postgres import publication
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import accept_policy, job_and_run, state

from koinon.catalog.entities import CatalogEntry
from koinon.catalog.repositories import local_catalog_entries
from koinon.integrations.content_sources.read_repository import SourceReadRepository

pytestmark = pytest.mark.integration


def folder(connection, identifier="managed", *, kind="collection"):
    connection.execute(
        "INSERT INTO lattice_catalog "
        "(id,tenant_id,workspace_id,project_id,parent_id,kind,name,description,status,"
        "metadata_json,created_by,updated_by,created_at,updated_at) "
        "VALUES(%s,'retained','workspace','project','folder',%s,'Managed','','ready',"
        "'{}','issuer|alice','issuer|alice',now(),now())",
        (identifier, kind),
    )


def prepare_folder(connection, *, event_failure=None):
    from koinon.integrations.content_sources.read_authority import source_authority
    from koinon.integrations.content_sources.sync_checkpoints import event_hash

    identity = SimpleNamespace(
        id="connection",
        tenant_id="retained",
        owner="issuer|alice",
        provider="google_drive",
        external_subject="provider-alice",
        external_tenant=None,
        issuer="https://accounts.google.com",
        config_fingerprint="f" * 64,
        scopes=["drive.readonly"],
    )
    authority, digest = source_authority(identity)
    connection.execute(
        "UPDATE koinon_content_connections SET config_fingerprint=%s,scopes=%s",
        ("f" * 64, Json(identity.scopes)),
    )
    connection.execute("UPDATE koinon_content_mappings SET config_fingerprint=%s", ("f" * 64,))
    connection.execute(
        "INSERT INTO koinon_content_policies(id,tenant_id,owner,mapping_id,revision,"
        "mapping_revision,authority_sha256,policy_json,policy_sha256,root_ancestry_json,review_id,"
        "review_digest,review_expires_at,created_at) VALUES('policy-mapping','retained','issuer|alice',"
        "'mapping',1,1,%s,%s,%s,'[\"root\"]','review',%s,now()+interval '1 day',now())",
        (digest, Json({"authority": authority}), "b" * 64, "c" * 64),
    )
    accept_policy(connection)
    state(connection)
    job_and_run(connection, "first")
    event = {
        "item": {
            "scope": {
                "account": {"provider": "google_drive", "subject": "provider-alice", "tenant_id": None},
                "drive_id": "drive",
            },
            "item_id": "remote-file",
            "name": "Managed",
            "kind": "folder",
            "version": "v1",
            "parents": ["root"],
            "mime_type": "folder/type",
            "size_bytes": None,
        },
        "ancestry": ["root"],
    }
    if event_failure == "not-object":
        event = []
    elif event_failure == "missing-mime":
        del event["item"]["mime_type"]
    elif event_failure == "wrong-scope":
        event["item"]["scope"]["drive_id"] = "foreign"
    digest = event_hash(event)
    connection.execute(
        "UPDATE koinon_content_objects SET remote_kind='folder',remote_name='Managed',"
        "remote_parent_id='root',remote_ancestry_json='[\"root\"]' WHERE id='origin'"
    )
    connection.execute(
        "INSERT INTO koinon_content_sync_work(id,tenant_id,mapping_id,object_id,generation,"
        "remote_version,event_sha256,status,expected_local_revision,expected_sha256,created_at,updated_at) "
        "VALUES('work','retained','mapping','origin',1,'v1',%s,'admitted','local-revision',%s,now(),now())",
        (digest, "b" * 64),
    )
    connection.execute(
        "INSERT INTO koinon_content_sync_observations VALUES('observation','retained',"
        "'mapping','first',1,0,'origin',1,'v1',%s,%s,'work',now())",
        (Json(event), digest),
    )
    connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=1 WHERE id='first'")


@pytest.fixture
async def retained_folder(source_sessions, source_database, request):
    sessions, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        for table in (
            "koinon_curated_source_roots",
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
            "koinon_content_folder_publications",
            "koinon_content_folder_bindings",
            "koinon_content_sync_observations",
            "koinon_content_sync_work",
            "koinon_content_policies",
            "koinon_content_sync_states",
            "lattice_domain_bindings",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
        parameter = getattr(request, "param", "collection")
        prepare_folder(
            connection, event_failure=parameter.get("event_failure") if isinstance(parameter, dict) else None
        )
        connection.execute("UPDATE lattice_catalog SET project_id=NULL WHERE id='workspace'")
        connection.execute("UPDATE lattice_catalog SET kind='collection' WHERE id='folder'")
        folder(connection, kind="collection" if isinstance(parameter, dict) else parameter)
        if not isinstance(parameter, dict) or parameter.get("publish", True):
            publication(connection)
        folder(connection, "child")
        connection.execute("UPDATE lattice_catalog SET parent_id='managed' WHERE id='child'")
    return sessions, uri


async def test_legacy_projection_excludes_retained_folder_and_descendants(retained_folder):
    sessions, uri = retained_folder
    for remove_binding in (False, True):
        if remove_binding:
            with (
                psycopg.connect(uri) as connection,
                pytest.raises(psycopg.errors.CheckViolation),
                connection.transaction(),
            ):
                connection.execute("DELETE FROM koinon_content_folder_bindings")
        async with sessions() as session:
            visible = set(
                await session.scalars(
                    select(CatalogEntry.id).where(
                        CatalogEntry.tenant_id == "retained", local_catalog_entries("retained", CatalogEntry)
                    )
                )
            )
        assert {"workspace", "project", "folder", "source", "asset"} <= visible
        assert not {"managed", "child"} & visible


async def test_descendant_identity_requires_retained_folder_publication_pin(retained_folder):
    sessions, _ = retained_folder
    async with sessions() as session:
        pins = await SourceReadRepository(session=session).entry_pins("retained", ("child",))
        assert len(pins) == 1
        pin = pins[0]
        assert (pin.folder_id, pin.publication_id, pin.observation_id, pin.canonical_revision) == (
            "managed",
            "publication",
            "observation",
            1,
        )


@pytest.mark.parametrize("retained_folder", ["folder", "collection", "corpus"], indirect=True)
async def test_current_folder_origin_resolves_exact_retained_remote_observation(retained_folder):
    sessions, _ = retained_folder
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        pins = await reader.entry_pins("retained", ("child",))
        origins = await reader.resolve("retained", pins)
        assert len(origins) == 1
        assert origins[0].pin == pins[0]
        assert (origins[0].target.item_id, origins[0].target.name, origins[0].target.parents) == (
            "remote-file",
            "Managed",
            ("root",),
        )


def publish_nested_folder(connection):
    from koinon.integrations.content_sources.sync_checkpoints import event_hash

    def clone(table, identifier, changes):
        connection.execute(
            sql.SQL(
                "INSERT INTO {table} SELECT (jsonb_populate_record(NULL::{table},"
                "to_jsonb(original)||%s::jsonb)).* FROM {table} original WHERE id=%s"
            ).format(table=sql.Identifier(table)),
            (Json(changes), identifier),
        )

    clone("lattice_catalog", "managed", {"id": "managed-child", "parent_id": "managed", "name": "Nested"})
    clone(
        "koinon_content_objects",
        "origin",
        {
            "id": "child-origin",
            "item_id": "remote-child",
            "remote_name": "Nested",
            "remote_parent_id": "remote-file",
            "remote_ancestry_json": ["root", "remote-file"],
            "published_sha256": None,
            "published_local_revision": None,
            "published_native_version_id": None,
        },
    )
    event = {
        "item": {
            "scope": {
                "account": {"provider": "google_drive", "subject": "provider-alice", "tenant_id": None},
                "drive_id": "drive",
            },
            "item_id": "remote-child",
            "name": "Nested",
            "kind": "folder",
            "version": "v1",
            "parents": ["remote-file"],
            "mime_type": "folder/type",
            "size_bytes": None,
        },
        "ancestry": ["root", "remote-file"],
    }
    digest = event_hash(event)
    clone(
        "koinon_content_sync_work",
        "work",
        {"id": "child-work", "object_id": "child-origin", "event_sha256": digest},
    )
    clone(
        "koinon_content_sync_observations",
        "observation",
        {
            "id": "child-observation",
            "object_id": "child-origin",
            "work_id": "child-work",
            "event_json": event,
            "event_sha256": digest,
            "page_sequence": 2,
        },
    )
    connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=2 WHERE id='first'")
    published = publication(
        connection,
        identifier="child-publication",
        observation="child-observation",
        folder_id="managed-child",
        complete=False,
        object_id="child-origin",
        work_id="child-work",
    )
    connection.execute(
        "INSERT INTO koinon_content_folder_bindings VALUES"
        "('retained','mapping','remote-child','managed-child','remote-file','managed','[\"root\",\"remote-file\"]',1,now())"
    )
    connection.execute(
        "UPDATE koinon_content_objects SET published_local_revision='1',published_sha256=%s "
        "WHERE id='child-origin'",
        (published["canonical_sha256"],),
    )


async def test_explicit_folder_pin_also_requires_every_managed_ancestor(retained_folder):
    sessions, uri = retained_folder
    with psycopg.connect(uri) as connection:
        publish_nested_folder(connection)
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        pins = await reader.entry_pins("retained", ("managed-child",))
        assert {pin.folder_id for pin in pins} == {"managed", "managed-child"}
        own = next(pin for pin in pins if pin.folder_id == "managed-child")
        origins = await reader.resolve("retained", (own,))
        assert {origin.pin.folder_id for origin in origins} == {"managed", "managed-child"}


async def test_folder_authority_queries_are_batched_without_canonical_payload(retained_folder):
    from sqlalchemy import event

    sessions, uri = retained_folder
    with psycopg.connect(uri) as connection:
        publish_nested_folder(connection)
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        pins = await reader.entry_pins("retained", ("managed-child",))
        parent = next(pin for pin in pins if pin.folder_id == "managed")
        statements = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().lower().startswith(("select", "with")):
                statements.append(statement)
                projection = statement
                assert "lattice_catalog.name" not in projection
                assert "lattice_catalog.description" not in projection
                assert "lattice_catalog.metadata_json" not in projection

        engine = session.sync_session.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            assert len(await reader.resolve("retained", (parent,))) == 1
            single = len(statements)
            statements.clear()
            assert len(await reader.resolve("retained", pins)) == 2
            assert len(statements) == single and single <= 4
        finally:
            event.remove(engine, "before_cursor_execute", capture)


@pytest.mark.parametrize(
    "retained_folder",
    [{"event_failure": failure} for failure in ("not-object", "missing-mime", "wrong-scope")],
    indirect=True,
)
async def test_malformed_retained_folder_observation_fails_closed(retained_folder):
    from koinon.integrations.content_sources.errors import SourceError

    sessions, _ = retained_folder
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        pins = await reader.entry_pins("retained", ("managed",))
        with pytest.raises(SourceError):
            await reader.resolve("retained", pins)


async def test_folder_pin_rejects_locally_reverted_name_without_new_publication(retained_folder):
    from koinon.integrations.content_sources.errors import SourceError

    sessions, uri = retained_folder
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        pins = await reader.entry_pins("retained", ("managed",))
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET name='Edited' WHERE id='managed'")
        connection.execute("UPDATE lattice_catalog SET name='Managed' WHERE id='managed'")
    async with sessions() as session:
        with pytest.raises(SourceError, match="version_changed"):
            await SourceReadRepository(session=session).resolve("retained", pins)


@pytest.mark.parametrize("identifier", ["managed", "folder", "project"])
async def test_folder_write_fence_locks_canonical_ancestry(retained_folder, identifier):
    sessions, uri = retained_folder
    async with sessions() as session:
        reader = SourceReadRepository(session=session)
        origins = await reader.resolve("retained", await reader.entry_pins("retained", ("managed",)))
        await reader.lock_origins("retained", origins, ())
        with (
            psycopg.connect(uri) as competing,
            pytest.raises(psycopg.errors.LockNotAvailable),
            competing.transaction(),
        ):
            competing.execute("SELECT id FROM lattice_catalog WHERE id=%s FOR UPDATE NOWAIT", (identifier,))
        await session.rollback()
        with psycopg.connect(uri) as competing:
            assert competing.execute(
                "SELECT id FROM lattice_catalog WHERE id=%s FOR UPDATE NOWAIT", (identifier,)
            ).fetchone() == (identifier,)


@pytest.fixture
async def folder_application(retained_folder):
    from datetime import UTC, datetime

    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.transaction import current_unit_of_work

    from koinon.catalog.entities import Membership
    from koinon.catalog.repositories import MembershipRepository
    from koinon.integrations.content_sources.read_authority import SourceReadAuthority
    from koinon.integrations.content_sources.reader_access import RemoteReadObservation
    from koinon.knowledge.bulk.authority import BulkAuthority
    from koinon.knowledge.bulk.repositories import BulkRepository
    from koinon.security.authority import primary_authority

    _, uri = retained_folder
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO koinon_content_connections SELECT (jsonb_populate_record("
            "NULL::koinon_content_connections,to_jsonb(c)||%s::jsonb)).* "
            "FROM koinon_content_connections c WHERE id='connection'",
            (Json({"id": "reader-connection", "owner": "reader", "external_subject": "provider-reader"}),),
        )
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": uri.replace("postgresql://", "postgresql+asyncpg://"),
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.jobs", "koinon.integrations.content_sources"):
        scan_package(package, context.container)
    context.register_bean(BulkAuthority)
    context.register_bean(BulkRepository)
    await context.start()
    try:
        async with primary_authority(read_only=False):
            await context.get_bean(MembershipRepository).save(
                Membership(id="reader", subject="reader", tenant_id="retained", role="admin")
            )

        class Remote:
            calls = []
            denied = False
            connections = SimpleNamespace(
                registrations=SimpleNamespace(get=lambda _: SimpleNamespace(fingerprint="f" * 64))
            )

            async def check(self, actor, tenant, identifier, targets):
                from koinon.integrations.content_sources.errors import SourceError

                unit = current_unit_of_work("primary")
                assert unit is None or unit.completed, "Provider called inside native unit"
                assert (actor, tenant, identifier) == ("reader", "retained", "reader-connection")
                self.calls.append(tuple(target.item_id for target in targets))
                if self.denied:
                    raise SourceError("access_denied")
                return tuple(RemoteReadObservation(target, datetime.now(UTC), 1) for target in targets)

        remote = Remote()
        context.get_bean(SourceReadAuthority).remote = remote
        yield context, remote, uri
    finally:
        await context.stop()


async def test_real_reader_browse_admits_folder_and_local_controls_then_revocation_hides_it(
    folder_application,
):
    from uuid import uuid4

    from koinon.catalog.browse import CatalogBrowse
    from koinon.catalog.browse_dtos import CatalogBrowseInput
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput, ReaderSourceSelection
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

    context, remote, _ = folder_application
    choices = context.get_bean(SourceReaderSelections)
    await choices.replace(
        "reader",
        "retained",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[ReaderSourceSelection(provider="google_drive", connection_id="reader-connection")],
        ),
    )
    browser = context.get_bean(CatalogBrowse)
    page = await browser.page("reader", "retained", CatalogBrowseInput(page_size=100))
    assert {item.id for item in page.items} >= {"managed", "child", "folder"}
    assert page.total is None and page.total_is_exact is False and remote.calls
    remote.denied = True
    page = await browser.page("reader", "retained", CatalogBrowseInput(page_size=100))
    assert "folder" in {item.id for item in page.items}
    assert not {"managed", "child"} & {item.id for item in page.items}


@pytest.mark.parametrize("change", ["selection", "disconnect", "local_edit", "ancestor_edit", "publication"])
async def test_real_read_fence_rejects_changes_before_payload_hydration(folder_application, change):
    from uuid import uuid4

    from test_source_folder_publication_postgres import observation_again

    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput, ReaderSourceSelection
    from koinon.integrations.content_sources.read_service import SourceReader
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

    context, remote, uri = folder_application
    choices = context.get_bean(SourceReaderSelections)
    await choices.replace(
        "reader",
        "retained",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[ReaderSourceSelection(provider="google_drive", connection_id="reader-connection")],
        ),
    )
    operation = await context.get_bean(SourceReader).entries("reader", "retained", ("child",))
    assert operation is not None and remote.calls
    if change == "selection":
        await choices.replace(
            "reader",
            "retained",
            ReaderSelectionInput(expected_revision=1, operation_id=uuid4(), connections=[]),
        )
    else:
        with psycopg.connect(uri) as connection:
            if change == "disconnect":
                connection.execute(
                    "UPDATE koinon_content_connections SET status='disconnected',revision=2,"
                    "secret_ciphertext=NULL WHERE id='reader-connection'"
                )
            elif change == "ancestor_edit":
                connection.execute("UPDATE lattice_catalog SET name='Moved ancestor' WHERE id='folder'")
            else:
                connection.execute("UPDATE lattice_catalog SET name='Renamed' WHERE id='managed'")
                connection.execute("UPDATE lattice_catalog SET name='Managed' WHERE id='managed'")
                if change == "publication":
                    observation_again(connection)
                    publication(connection, identifier="next", observation="second", previous="publication")
    hydrated = False
    with pytest.raises(SourceError):
        async with operation.read_fence():
            await context.get_bean(CatalogService).get("reader", "retained", "child")
            hydrated = True
    assert not hydrated


async def test_legacy_audit_excludes_managed_history_before_search_and_totals(folder_application):
    from koinon.catalog.service import CatalogService

    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        for identifier, resource, details in (
            ("audit-local", "folder", {"label": "Local"}),
            ("audit-hidden", "managed", {"old_name": "Secret remote title"}),
            ("audit-child", "child", {"old_path": "Secret remote path"}),
            ("audit-receipt", "mapping", {"work_id": "opaque-work"}),
        ):
            connection.execute(
                "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
                "VALUES(%s,'retained','reader','catalog.updated',%s,%s,now())",
                (identifier, resource, Json(details)),
            )
    service = context.get_bean(CatalogService)
    page = await service.audit_page("reader", "retained", action="catalog.updated")
    assert page["total"] == 1
    assert {row.id for row in page["items"]} == {"audit-local"}
    assert (await service.audit_page("reader", "retained", action="catalog.updated", q="Managed"))[
        "total"
    ] == 0
    all_rows = await service.audit("reader", "retained")
    assert not {"audit-hidden", "audit-child"} & {row.id for row in all_rows}


async def test_audit_projects_exact_policy_receipt_and_discards_untrusted_details(folder_application):
    from koinon.catalog.service import CatalogService

    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        receipt, operation, policy, revision = connection.execute(
            "SELECT id,operation_id,policy_id,result_policy_revision FROM koinon_content_policy_operations"
        ).fetchone()
        details = {
            "receipt_id": receipt,
            "operation_id": operation,
            "policy_id": "forged-policy",
            "revision": 999,
            "secret_title": "Protected remote title",
        }
        for identifier, owner, values in (
            ("safe-policy", "issuer|alice", details),
            ("wrong-owner", "reader", details),
            ("wrong-operation", "issuer|alice", {**details, "operation_id": "forged"}),
        ):
            connection.execute(
                "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
                "VALUES(%s,'retained',%s,'source.policy.apply','mapping',%s,now())",
                (identifier, owner, Json(values)),
            )
    service = context.get_bean(CatalogService)
    page = await service.audit_page("reader", "retained", action="source.policy.apply")
    assert page["total"] == 1 and [row.id for row in page["items"]] == ["safe-policy"]
    assert page["items"][0].details == {
        "receipt_id": receipt,
        "operation_id": operation,
        "policy_id": policy,
        "revision": revision,
    }
    assert (await service.audit_page("reader", "retained", q="Protected remote title"))["total"] == 0
    assert [row.id for row in await service.audit("reader", "retained")] == ["safe-policy"]
    with psycopg.connect(uri) as connection:
        assert (
            connection.execute("SELECT details FROM lattice_audit WHERE id='safe-policy'").fetchone()[0]
            == details
        )


@pytest.mark.parametrize("kind", ["membership", "connection", "control"])
async def test_safe_audit_controls_project_only_closed_fields(folder_application, kind):
    from test_source_controls_postgres import receipt

    from koinon.catalog.service import CatalogService

    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        if kind == "membership":
            action, resource, owner = "membership.updated", "reader", "reader"
            details = {"role": "viewer", "active": False, "name": "Secret title"}
            expected = {"role": "viewer", "active": False}
        elif kind == "connection":
            action, resource, owner = "source.connected", "connection", "issuer|alice"
            details = {
                "provider": "Secret title",
                "revision": 1,
                "outcome": "success",
                "name": "Secret title",
            }
            expected = {"provider": "google_drive", "revision": 1, "outcome": "success"}
        else:
            result = receipt(connection, result_changes={"disposition": "paused"})
            action, resource, owner = "source.pause", "mapping", "issuer|alice"
            details = {**result, "outcome": "Secret title", "name": "Secret title"}
            expected = {
                "receipt_id": result["receipt_id"],
                "operation_id": result["operation_id"],
                "control_revision": 2,
                "outcome": "paused",
            }
        connection.execute(
            "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
            "VALUES('safe-control','retained',%s,%s,%s,%s,now())",
            (owner, action, resource, Json(details)),
        )
    page = await context.get_bean(CatalogService).audit_page("reader", "retained", action=action)
    assert page["total"] == 1 and len(page["items"]) == 1
    assert page["items"][0].details == expected
    assert (await context.get_bean(CatalogService).audit_page("reader", "retained", q="Secret title"))[
        "total"
    ] == 0


async def test_local_entry_move_into_managed_ancestry_cannot_reuse_local_admission(folder_application):
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_service import SourceReader

    context, remote, uri = folder_application
    with psycopg.connect(uri) as connection:
        folder(connection, "loose")
    reader = context.get_bean(SourceReader)
    operation = await reader.entries("reader", "retained", ("loose",))
    assert operation is not None, "Local identity needs a fence against concurrent reclassification"
    async with operation.read_fence():
        assert (await context.get_bean(CatalogService).get("reader", "retained", "loose")).name == "Managed"
    assert not remote.calls
    operation = await reader.entries("reader", "retained", ("loose",))
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET parent_id='managed' WHERE id='loose'")
    with pytest.raises(SourceError):
        async with operation.read_fence():
            pytest.fail("Local admission survived a move into protected source ancestry")


async def test_local_membership_revocation_denies_before_payload_sql(folder_application):
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.read_service import SourceReader

    context, remote, uri = folder_application
    operation = await context.get_bean(SourceReader).entries("reader", "retained", ("folder",))
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_memberships SET active=false WHERE id='reader'")

    def forbid_payload(connection, cursor, statement, parameters, execution_context, executemany):
        projection = statement
        assert "lattice_catalog.name" not in projection, "Revoked local reader hydrated canonical names"
        assert "lattice_catalog.metadata_json" not in projection

    event.listen(Engine, "before_cursor_execute", forbid_payload)
    try:
        with pytest.raises(AccessDenied):
            async with operation.read_fence():
                await context.get_bean(CatalogService).get("reader", "retained", "folder")
    finally:
        event.remove(Engine, "before_cursor_execute", forbid_payload)
    assert not remote.calls


async def test_local_edit_requires_fresh_admission_and_remains_usable(folder_application):
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_service import SourceReader

    context, remote, uri = folder_application
    reader = context.get_bean(SourceReader)
    operation = await reader.entries("reader", "retained", ("folder",))
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET name='Updated local folder' WHERE id='folder'")
    with pytest.raises(SourceError, match="authority_changed"):
        async with operation.read_fence():
            pytest.fail("Old admission survived a local edit")
    fresh = await reader.entries("reader", "retained", ("folder",))
    async with fresh.read_fence():
        entry = await context.get_bean(CatalogService).get("reader", "retained", "folder")
        assert entry.name == "Updated local folder"
    assert not remote.calls


async def test_local_admission_refreshes_corporate_membership_before_read_snapshot(folder_application):
    from datetime import UTC, datetime, timedelta

    from pyfly.data.transaction import current_unit_of_work

    from koinon.catalog.ports import ManagedMembership
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.read_service import SourceReader

    context, remote, uri = folder_application
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_memberships SET active=false WHERE id='reader'")
    refreshed = False

    class Directory:
        async def load_managed_memberships(self, subject):
            nonlocal refreshed
            if current_unit_of_work("primary") is None:
                refreshed = True
            if not refreshed:
                return []
            now = datetime.now(UTC)
            return [
                ManagedMembership(
                    id="corporate-reader",
                    subject=subject,
                    tenant_id="retained",
                    workspace_id=None,
                    role="admin",
                    active=True,
                    created_at=now,
                    source_id="directory",
                    source_name="Directory",
                    expires_at=now + timedelta(minutes=5),
                )
            ]

    catalog = context.get_bean(CatalogService)
    catalog._managed_provider = None
    catalog._managed_memberships = Directory()
    operation = await context.get_bean(SourceReader).entries("reader", "retained", ("folder",))
    async with operation.read_fence():
        assert (await catalog.get("reader", "retained", "folder")).id == "folder"
    assert not remote.calls


async def test_managed_to_local_move_invalidates_prior_admission(folder_application):
    from uuid import uuid4

    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput, ReaderSourceSelection
    from koinon.integrations.content_sources.read_service import SourceReader
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

    context, _, uri = folder_application
    await context.get_bean(SourceReaderSelections).replace(
        "reader",
        "retained",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[ReaderSourceSelection(provider="google_drive", connection_id="reader-connection")],
        ),
    )
    reader = context.get_bean(SourceReader)
    operation = await reader.entries("reader", "retained", ("child",))
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET parent_id='folder' WHERE id='child'")
    with pytest.raises(SourceError, match="authority_changed"):
        async with operation.read_fence():
            pytest.fail("Prior source admission survived a change to local ancestry")


@pytest.mark.parametrize("kind", ["document", "dataset"])
async def test_retained_local_reference_inherits_folder_authority(folder_application, kind):
    from uuid import uuid4

    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_dtos import (
        LocalFolderSourcePin,
        ReaderSelectionInput,
        ReaderSourceSelection,
    )
    from koinon.integrations.content_sources.read_service import SourceReader
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

    context, remote, uri = folder_application
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET kind=%s WHERE id='child'", (kind,))
    reference = SimpleNamespace(
        id="retained-reference",
        asset_id="child",
        kind=kind,
        knowledge_version_id=None,
        source_version_id="native-version",
        extraction_id="extraction",
        source_part_id=None,
        snapshot_id="snapshot",
        query_id=None,
    )
    reader = context.get_bean(SourceReader)
    with pytest.raises(SourceError, match="reconnect_required"):
        await reader.sources("reader", "retained", (reference,))
    assert not remote.calls
    await context.get_bean(SourceReaderSelections).replace(
        "reader",
        "retained",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[ReaderSourceSelection(provider="google_drive", connection_id="reader-connection")],
        ),
    )
    operation = await reader.sources("reader", "retained", (reference,))
    assert {pin.folder_id for pin in operation.used if isinstance(pin, LocalFolderSourcePin)} == {"managed"}
    async with operation.read_fence():
        pass
    await operation.release()
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET parent_id='folder' WHERE id='child'")
    with pytest.raises(SourceError, match="authority_changed"):
        async with operation.read_fence():
            pytest.fail("Saved reference admission survived a change to source ancestry")


async def test_ordinary_local_reference_remains_usable_with_an_ancestry_fence(folder_application):
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_service import SourceReader

    context, remote, uri = folder_application
    with psycopg.connect(uri) as connection:
        folder(connection, "local-document")
        connection.execute("UPDATE lattice_catalog SET kind='document' WHERE id='local-document'")
    reference = SimpleNamespace(
        id="local-reference",
        asset_id="local-document",
        kind="document",
        knowledge_version_id=None,
        source_version_id="local-version",
        extraction_id="local-extraction",
        source_part_id=None,
        snapshot_id=None,
        query_id=None,
    )
    operation = await context.get_bean(SourceReader).sources("reader", "retained", (reference,))
    async with operation.read_fence():
        entry = await context.get_bean(CatalogService).get("reader", "retained", "local-document")
        assert entry.kind == "document" and entry.parent_id == "folder"
    await operation.release()
    assert not operation.used and not remote.calls
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE lattice_catalog SET parent_id='managed' WHERE id='local-document'")
    with pytest.raises(SourceError, match="authority_changed"):
        async with operation.read_fence():
            pytest.fail("Local saved reference was reclassified without fresh source admission")


async def test_audit_history_stays_protected_after_authorized_move_to_local_parent(folder_application):
    from uuid import uuid4

    from koinon.catalog.hierarchy_service import CatalogHierarchyService
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput, ReaderSourceSelection
    from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections

    context, _, uri = folder_application
    await context.get_bean(SourceReaderSelections).replace(
        "reader",
        "retained",
        ReaderSelectionInput(
            expected_revision=0,
            operation_id=uuid4(),
            connections=[ReaderSourceSelection(provider="google_drive", connection_id="reader-connection")],
        ),
    )
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
            "VALUES('protected-history','retained','reader','catalog.updated','child',%s,now())",
            (Json({"old_name": "Source-derived historical title"}),),
        )
        expected = connection.execute("SELECT updated_at FROM lattice_catalog WHERE id='child'").fetchone()[0]
        assert connection.execute(
            "SELECT coverage FROM koinon_catalog_history_identities WHERE resource_id='child'"
        ).fetchone() == ("complete",)
    await context.get_bean(CatalogHierarchyService).move(
        "reader",
        "retained",
        "child",
        parent_id="folder",
        expected_parent_id="managed",
        expected_updated_at=expected,
    )
    service = context.get_bean(CatalogService)
    page = await service.audit_page("reader", "retained", action="catalog.updated")
    assert page["total"] == 0 and not page["items"]
    assert (await service.audit_page("reader", "retained", action="catalog.updated", q="Managed"))[
        "total"
    ] == 0
    assert not [row for row in await service.audit("reader", "retained") if row.id == "protected-history"]
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT count(*) FROM lattice_audit WHERE id='protected-history'"
        ).fetchone() == (1,)


async def test_folder_authority_requires_reader_and_rechecks_publication_after_remote(
    retained_folder, monkeypatch
):
    from datetime import UTC, datetime

    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_authority import SourceReadAuthority
    from koinon.integrations.content_sources.read_dtos import ReaderSourceSelection
    from koinon.integrations.content_sources.reader_access import RemoteReadObservation

    sessions, uri = retained_folder
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO koinon_content_connections SELECT (jsonb_populate_record("
            "NULL::koinon_content_connections,to_jsonb(c)||"
            '\'{"id":"reader-connection","owner":"reader","external_subject":"provider-reader"}\'::jsonb)).* '
            "FROM koinon_content_connections c WHERE id='connection'"
        )
    async with sessions() as session:

        @asynccontextmanager
        async def unit(**kwargs):
            if session.in_transaction():
                yield
            else:
                async with session.begin():
                    yield

        monkeypatch.setattr("koinon.integrations.content_sources.read_authority.primary_authority", unit)

        class Catalog:
            async def _refresh_managed_memberships(self, actor):
                pass

            async def get_identity(self, actor, tenant, identifier):
                return (
                    await session.execute(
                        select(CatalogEntry.id, CatalogEntry.parent_id, CatalogEntry.status).where(
                            CatalogEntry.tenant_id == tenant, CatalogEntry.id == identifier
                        )
                    )
                ).one()

            async def get(self, *args):
                pytest.fail("Canonical folder payload was hydrated before authority")

        class Remote:
            mutate = False
            calls = []
            connections = SimpleNamespace(
                registrations=SimpleNamespace(get=lambda _: SimpleNamespace(fingerprint="f" * 64))
            )

            async def check(self, actor, tenant, identifier, targets):
                assert not session.in_transaction(), "Provider I/O occurred inside local unit"
                self.calls.append(identifier)
                if self.mutate:
                    with psycopg.connect(uri) as connection:
                        connection.execute(
                            "UPDATE lattice_catalog SET description='Edited' WHERE id='managed'"
                        )
                return tuple(RemoteReadObservation(target, datetime.now(UTC), 1) for target in targets)

        records = SourceReadRepository(session=session)
        async with unit():
            pins = await records.entry_pins("retained", ("child",))
        remote = Remote()
        authority = SourceReadAuthority(records, remote, Catalog())
        choices = (ReaderSourceSelection(provider="google_drive", connection_id="reader-connection"),)
        with pytest.raises(SourceError, match="reconnect_required"):
            await authority.check("reader", "retained", pins, ())
        assert not remote.calls
        await authority.check("reader", "retained", pins, choices)
        assert remote.calls == ["reader-connection"]
        remote.mutate = True
        with pytest.raises(SourceError, match="version_changed"):
            await authority.check("reader", "retained", pins, choices)


@pytest.mark.parametrize("ancestor_failure", ["moved", "cycle", "missing", "root_moved"])
async def test_reader_folder_check_requires_exact_structure_and_own_connection(ancestor_failure):
    from dataclasses import replace

    from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.reader_access import PersonalSourceAccess, RemoteFolderReadTarget

    account = Account("google_drive", "provider-reader", None)
    scope = SourceScope(account, "drive")
    current = RemoteItem(scope, "remote-folder", "Folder", "folder", "v1", None, "folder/type", ("inner",))
    nodes = {
        "drive-root": RemoteItem(scope, "drive-root", "Drive", "folder", "d1", None, "folder/type", ()),
        "root": RemoteItem(scope, "root", "Root", "folder", "r1", None, "folder/type", ("drive-root",)),
        "inner": RemoteItem(scope, "inner", "Inner", "folder", "i1", None, "folder/type", ("root",)),
    }
    calls = []

    class Connections:
        async def connected(self, actor, tenant, identifier):
            calls.append((actor, tenant, identifier))
            assert (actor, identifier) == ("reader", "reader-connection")
            return SimpleNamespace(account=account)

        async def read_grant(self, *args):
            return SimpleNamespace(token="synthetic", revision=7)

        async def confirm_read_grant(self, *args):
            pass

    class Browser:
        @asynccontextmanager
        async def _source(self, requested_scope, tokens):
            assert requested_scope == scope
            yield self

        async def check_access(self, identifier):
            raise SourceError("unsupported")

        async def root(self):
            return nodes["drive-root"]

        async def get_item(self, identifier):
            if identifier == "remote-folder":
                return current
            if identifier not in nodes:
                raise SourceError("access_denied")
            return nodes[identifier]

    access = PersonalSourceAccess(Browser(), Connections())
    target = RemoteFolderReadTarget(
        "google_drive",
        "drive",
        "remote-folder",
        "v1",
        name="Folder",
        parents=("inner",),
        mime_type="folder/type",
        size_bytes=None,
        ancestry=("root", "inner"),
        root_ancestry=("root", "drive-root"),
    )
    result = await access.check("reader", "tenant", "reader-connection", (target,))
    assert result[0].connection_revision == 7 and result[0].target == target
    for changes in ({"name": "Renamed"}, {"parents": ("other",)}, {"kind": "file"}, {"version": "v2"}):
        current = replace(current, **changes)
        with pytest.raises(SourceError):
            await access.check("reader", "tenant", "reader-connection", (target,))
        current = RemoteItem(
            scope, "remote-folder", "Folder", "folder", "v1", None, "folder/type", ("inner",)
        )
    assert len(calls) == 5
    if ancestor_failure == "moved":
        nodes["inner"] = replace(nodes["inner"], parents=("drive-root",))
    elif ancestor_failure == "cycle":
        nodes["inner"] = replace(nodes["inner"], parents=("inner",))
    elif ancestor_failure == "missing":
        del nodes["inner"]
    else:
        nodes["root"] = replace(nodes["root"], parents=())
    with pytest.raises(SourceError):
        await access.check("reader", "tenant", "reader-connection", (target,))


async def test_folder_ancestor_budget_is_shared_across_drives_before_remote_reads():
    from koinon.integrations.content_sources.dtos import Account, RemoteItem
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.reader_access import PersonalSourceAccess, RemoteFolderReadTarget

    account = Account("google_drive", "reader-subject", None)
    ancestry_reads = []
    chain = tuple(f"node-{index}" for index in range(256))

    class Connections:
        async def connected(self, *args):
            return SimpleNamespace(account=account)

        async def read_grant(self, *args):
            return SimpleNamespace(token="synthetic", revision=1)

        async def confirm_read_grant(self, *args):
            pass

    class Adapter:
        def __init__(self, scope):
            self.scope = scope

        async def check_access(self, identifier):
            raise SourceError("unsupported")

        async def root(self):
            ancestry_reads.append((self.scope.drive_id, chain[0]))
            return RemoteItem(self.scope, chain[0], "Root", "folder", "v1", None, None, ())

        async def get_item(self, identifier):
            if identifier == "folder":
                return RemoteItem(self.scope, identifier, "Folder", "folder", "v1", None, None, (chain[-1],))
            ancestry_reads.append((self.scope.drive_id, identifier))
            index = chain.index(identifier)
            return RemoteItem(
                self.scope, identifier, "Parent", "folder", "v1", None, None, (chain[index - 1],)
            )

    class Browser:
        @asynccontextmanager
        async def _source(self, scope, tokens):
            yield Adapter(scope)

    targets = tuple(
        RemoteFolderReadTarget(
            "google_drive",
            drive,
            "folder",
            "v1",
            name="Folder",
            parents=(chain[-1],),
            mime_type=None,
            size_bytes=None,
            ancestry=chain,
            root_ancestry=(chain[0],),
        )
        for drive in ("first", "second", "third")
    )
    with pytest.raises(SourceError, match="size_exceeded"):
        await PersonalSourceAccess(Browser(), Connections()).check("reader", "tenant", "connection", targets)
    assert len(ancestry_reads) == 512
    assert {drive for drive, _ in ancestry_reads} == {"first", "second"}


@pytest.mark.parametrize("native_imported", [False, True])
async def test_structured_glossary_admission_distinguishes_folder_and_native_pins(native_imported):
    from koinon.integrations.content_sources.read_dtos import LocalFolderSourcePin, LocalSourcePin
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
    from koinon.knowledge.native_provenance import StructuredSourceAdmission

    pins = {LocalFolderSourcePin("folder", "publication", "observation", 1)}
    if native_imported:
        pins.add(LocalSourcePin("dataset", "structured", "workspace", "native", "snapshot"))
    admission = StructuredSourceAdmission(
        NativeEvidenceReceipt("reader", "tenant"),
        SimpleNamespace(tenant="tenant", actor="reader", used=pins),
        "dataset",
        SimpleNamespace(native_workspace_id="workspace", native_id="native"),
    )
    row = {"term": "Revenue", "columns": ["orders.total"], "metrics": []}
    result = await admission.admit(
        "glossary",
        [row],
        SimpleNamespace(tenant_id="tenant", workspace_id="workspace", dataset_id="native", actor="reader"),
    )
    assert result == (() if native_imported else (row,))

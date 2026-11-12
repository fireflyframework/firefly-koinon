# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Forward metadata provenance migrations against a separately versioned real database."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.script import ScriptDirectory
from psycopg.types.json import Jsonb

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "metadata_source_fixture",
    Path(__file__).parents[1] / "integrations/content_sources/test_source_migration_postgres.py",
)
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
source_database = _fixture.source_database


@pytest.fixture
def metadata_database(source_database):
    target, role, engine = source_database
    with engine.connect() as connection:
        config = _fixture.load("deploy/migrate.py").history_config(
            "structured", ROOT / "packages/structured/migrations/versions", connection
        )
        command.upgrade(config, "head")
        connection.commit()
    return target.set(drivername="postgresql").render_as_string(hide_password=False), role, engine


def published_query(connection):
    identifier, workspace = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO flyquery_queries(id,tenant_id,workspace_id,question,consumer_context,finalised_at) "
        "VALUES(%s,'tenant',%s,'Question',%s,now())",
        (identifier, workspace, Jsonb({"actor": "reader"})),
    )
    return identifier


def test_published_query_cannot_change_consumer_authority(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        identifier = published_query(connection)
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="published query authority"),
            connection.transaction(),
        ):
            connection.execute("UPDATE flyquery_queries SET consumer_context='{}' WHERE id=%s", (identifier,))


def glossary(connection, *, workspace=None, term=None):
    identifier, workspace = uuid4(), workspace or uuid4()
    connection.execute(
        "INSERT INTO "
        "flyquery_glossary_terms(id,tenant_id,workspace_id,term,definition) "
        "VALUES(%s,'tenant',%s,%s,'Definition')",
        (identifier, workspace, term or str(identifier)),
    )
    return identifier, workspace


def provenance(connection, entity, workspace, *, size=1, ordinal=0, operation=None, manifest=None, bind=True):
    identifier, operation = uuid4(), operation or uuid4()
    manifest = manifest or {
        "schema": "koinon.structured-metadata-provenance.v1",
        "complete": True,
        "tables": [],
        "provenance_ids": [],
        "query_ids": [],
    }
    connection.execute(
        "INSERT INTO flyquery_metadata_provenance(id,tenant_id,workspace_id,entity_kind,entity_id,"
        "payload_json,payload_sha256,manifest_json,manifest_sha256,created_by,producer_kind,"
        "producer_operation_id,producer_ordinal,producer_size,request_sha256) "
        "SELECT "
        "%s,tenant_id,workspace_id,'glossary',id,public.koinon_metadata_payload('glossary',to_jsonb(t)),"
        "public.koinon_json_sha256(public.koinon_metadata_payload('glossary',to_jsonb(t))),%s,"
        "public.koinon_json_sha256(%s),'reader','manual',%s,%s,%s,repeat('a',64) "
        "FROM flyquery_glossary_terms t WHERE id=%s AND workspace_id=%s",
        (identifier, Jsonb(manifest), Jsonb(manifest), operation, ordinal, size, entity, workspace),
    )
    if bind:
        connection.execute(
            "UPDATE flyquery_glossary_terms SET source_provenance_id=%s WHERE id=%s", (identifier, entity)
        )
    return identifier


def test_provenance_payload_and_row_binding_are_immutable(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        entity, workspace = glossary(connection)
        identifier = provenance(connection, entity, workspace)
        connection.commit()
        for statement in (
            "UPDATE flyquery_glossary_terms SET definition='Forged' WHERE id=%s",
            "UPDATE flyquery_glossary_terms SET source_provenance_id=NULL WHERE id=%s",
            "UPDATE flyquery_metadata_provenance SET payload_json='{}' WHERE entity_id=%s",
            "DELETE FROM flyquery_metadata_provenance WHERE entity_id=%s",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement, (entity,))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("TRUNCATE flyquery_metadata_provenance CASCADE")
        other, _ = glossary(connection, workspace=workspace)
        with pytest.raises(psycopg.errors.CheckViolation, match="binding mismatch"), connection.transaction():
            connection.execute(
                "UPDATE flyquery_glossary_terms SET source_provenance_id=%s WHERE id=%s", (identifier, other)
            )
        assert connection.execute(
            "SELECT definition FROM flyquery_glossary_terms WHERE id=%s", (entity,)
        ).fetchone() == ("Definition",)


@pytest.mark.parametrize("size,bind", [(2, True), (1, False)])
def test_incomplete_producer_or_unbound_effect_rolls_back(metadata_database, size, bind):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="metadata producer"),
            connection.transaction(),
        ):
            entity, workspace = glossary(connection)
            provenance(connection, entity, workspace, size=size, bind=bind)
        assert connection.execute("SELECT count(*) FROM flyquery_metadata_provenance").fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM flyquery_glossary_terms").fetchone() == (0,)


def test_complete_producer_group_is_atomic_and_replay_identity_unique(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        operation, workspace = uuid4(), uuid4()
        entities = [glossary(connection, workspace=workspace)[0] for _ in range(2)]
        for ordinal, entity in enumerate(entities):
            provenance(connection, entity, workspace, size=2, ordinal=ordinal, operation=operation)
        connection.commit()
        assert connection.execute("SELECT count(*) FROM flyquery_metadata_provenance").fetchone() == (2,)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            provenance(connection, entities[0], workspace, size=2, operation=operation)


@pytest.mark.parametrize(
    "change",
    [
        {"complete": False},
        {"tables": [{"dataset_id": str(uuid4()), "table_id": str(uuid4()), "snapshot_id": str(uuid4())}]},
        {"provenance_ids": [str(uuid4())]},
        {"query_ids": [str(uuid4())]},
        {"untrusted": "extra"},
    ],
)
def test_unresolved_or_incomplete_manifest_is_not_authority(metadata_database, change):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        entity, workspace = glossary(connection)
        manifest = {
            "schema": "koinon.structured-metadata-provenance.v1",
            "complete": True,
            "tables": [],
            "provenance_ids": [],
            "query_ids": [],
            **change,
        }
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            provenance(connection, entity, workspace, manifest=manifest)
        assert connection.execute(
            "SELECT source_provenance_id FROM flyquery_glossary_terms WHERE id=%s", (entity,)
        ).fetchone() == (None,)


def test_runtime_role_cannot_mutate_or_cross_workspace_provenance(metadata_database):
    from psycopg import sql

    uri, role, _ = metadata_database
    with psycopg.connect(uri) as connection:
        entity, workspace = glossary(connection)
        provenance(connection, entity, workspace)
        connection.commit()
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        connection.execute(
            sql.SQL("GRANT ALL ON flyquery_metadata_provenance TO {}").format(sql.Identifier(role))
        )
        connection.execute(
            sql.SQL("GRANT UPDATE(payload_json) ON flyquery_metadata_provenance TO {}").format(
                sql.Identifier(role)
            )
        )
        _fixture.load("deploy/provision_roles.py").grant_table(
            connection, "flyquery_metadata_provenance", role
        )
        _fixture.load("deploy/provision_roles.py").grant_table(connection, "flyquery_glossary_terms", role)
        assert connection.execute(
            "SELECT has_table_privilege(%s,'flyquery_metadata_provenance','INSERT'),"
            "has_any_column_privilege(%s,'flyquery_metadata_provenance','UPDATE'),"
            "has_table_privilege(%s,'flyquery_metadata_provenance','DELETE'),"
            "has_table_privilege(%s,'flyquery_metadata_provenance','TRUNCATE')",
            (role,) * 4,
        ).fetchone() == (True, False, False, False)
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        connection.execute(
            "SELECT set_config('app.tenant_id','tenant',true),set_config('app.workspace_id',%s,true)",
            (str(workspace),),
        )
        assert connection.execute("SELECT count(*) FROM flyquery_metadata_provenance").fetchone() == (1,)
        connection.execute("SELECT set_config('app.workspace_id',%s,true)", (str(uuid4()),))
        assert connection.execute("SELECT count(*) FROM flyquery_metadata_provenance").fetchone() == (0,)
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
            connection.execute("DELETE FROM flyquery_metadata_provenance")
        connection.execute("SELECT set_config('app.workspace_id',%s,true)", (str(workspace),))
        new_entity, _ = glossary(connection, workspace=workspace)
        provenance(connection, new_entity, workspace)
        connection.commit()
        assert connection.execute("SELECT count(*) FROM flyquery_metadata_provenance").fetchone() == (2,)


def test_provenance_lookup_uses_scope_index_at_ten_thousand_rows(metadata_database):
    uri, _, _ = metadata_database
    workspace = uuid4()
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO flyquery_glossary_terms(id,tenant_id,workspace_id,term,definition) "
            "SELECT gen_random_uuid(),'tenant',%s,'term-'||n,'Definition' FROM generate_series(1,10000) n",
            (workspace,),
        )
        connection.execute("""INSERT INTO flyquery_metadata_provenance
            (id,tenant_id,workspace_id,entity_kind,entity_id,payload_json,payload_sha256,manifest_json,manifest_sha256,
             created_by,producer_kind,producer_operation_id,producer_ordinal,producer_size,request_sha256)
            SELECT gen_random_uuid(),tenant_id,workspace_id,'glossary',id,
              public.koinon_metadata_payload('glossary',to_jsonb(t)),
              public.koinon_json_sha256(public.koinon_metadata_payload('glossary',to_jsonb(t))),
              m,public.koinon_json_sha256(m),'reader','manual',gen_random_uuid(),0,1,repeat('a',64)
            FROM flyquery_glossary_terms t CROSS JOIN (SELECT
              '{"schema":"koinon.structured-metadata-provenance.v1","complete":true,
                "tables":[],"provenance_ids":[],"query_ids":[]}'::jsonb m) manifest""")
        connection.execute(
            "UPDATE flyquery_glossary_terms t SET source_provenance_id=p.id FROM "
            "flyquery_metadata_provenance p WHERE p.entity_id=t.id"
        )
        connection.commit()
        connection.execute("ANALYZE flyquery_metadata_provenance")
        entity = connection.execute(
            "SELECT id FROM flyquery_glossary_terms WHERE term='term-9999'"
        ).fetchone()[0]
        plan = connection.execute(
            "EXPLAIN(ANALYZE,FORMAT JSON) SELECT id FROM flyquery_metadata_provenance "
            "WHERE tenant_id='tenant' AND workspace_id=%s AND entity_kind='glossary' AND entity_id=%s",
            (workspace, entity),
        ).fetchone()[0][0]["Plan"]
        assert plan["Actual Rows"] == 1
        assert plan["Index Name"] == "ix_metadata_provenance_scope"


def replacement_dataset(connection):
    workspace, dataset, file_id, table, snapshot = (uuid4() for _ in range(5))
    connection.execute(
        "INSERT INTO flyquery_workspaces(id,tenant_id,slug,name) VALUES(%s,'tenant',%s,'Workspace')",
        (workspace, str(workspace)),
    )
    connection.execute(
        "INSERT INTO flyquery_datasets(id,tenant_id,workspace_id,name) VALUES(%s,'tenant',%s,'Dataset')",
        (dataset, workspace),
    )
    connection.execute(
        "INSERT INTO "
        "flyquery_files(id,tenant_id,workspace_id,dataset_id,original_filename,file_for"
        "mat,size_bytes,content_hash_sha256,object_store_key,uploaded_by,status) "
        "VALUES(%s,'tenant',%s,%s,'data.csv','csv',7,%s,'private/key','reader','PARSED'"
        ")",
        (file_id, workspace, dataset, "b" * 64),
    )
    connection.execute(
        "INSERT INTO "
        "flyquery_tables(id,tenant_id,workspace_id,dataset_id,source_file_id,name,quali"
        "fied_name) VALUES(%s,'tenant',%s,%s,%s,'data','data')",
        (table, workspace, dataset, file_id),
    )
    connection.execute(
        "INSERT INTO "
        "flyquery_schema_snapshots(id,tenant_id,workspace_id,dataset_id,table_id,snapsh"
        "ot_hash,n_columns,status,triggered_by,created_by) "
        "VALUES(%s,'tenant',%s,%s,%s,'snapshot',1,'READY','USER','reader')",
        (snapshot, workspace, dataset, table),
    )
    connection.execute("UPDATE flyquery_tables SET current_snapshot_id=%s WHERE id=%s", (snapshot, table))
    baseline = {
        "schema": "koinon.dataset-replacement-baseline.v1",
        "source_attempt_id": "attempt",
        "imported_version_id": "attempt",
        "native_file_id": str(file_id),
        "catalog_file_version_id": "catalog-old",
        "source_generation": 1,
        "policy_id": "policy",
        "policy_revision": 1,
        "dataset_id": str(dataset),
        "catalog_dataset_id": "catalog-dataset",
        "local_revision": "revision-1",
        "sha256": "b" * 64,
        "members": [
            {
                "member_key": "root",
                "table_id": str(table),
                "catalog_table_id": "catalog-table",
                "snapshot_id": str(snapshot),
                "source_file_id": str(file_id),
                "local_revision": "revision-1",
                "sha256": "b" * 64,
            }
        ],
    }
    return workspace, dataset, baseline


def bulk_operation(
    connection, workspace, dataset, *, kind="initial", baseline=None, operation=None, file_id=None
):
    operation, file_id = operation or uuid4(), file_id or uuid4()
    connection.execute(
        "INSERT INTO "
        "flyquery_bulk_operations(id,tenant_id,workspace_id,dataset_id,file_id,actor,catalog_source_id,"
        "catalog_dataset_id,catalog_file_version_id,filename,sha256,size_bytes,status,c"
        "reated_at,operation_kind,baseline_json,baseline_sha256) "
        "VALUES(%s,'tenant',%s,%s,%s,'reader','catalog-source','catalog-dataset',%s,'da"
        "ta.csv',%s,8,'admitted',now(),%s,%s,public.koinon_json_sha256(%s))",
        (
            operation,
            workspace,
            dataset,
            file_id,
            str(operation),
            "c" * 64,
            kind,
            Jsonb(baseline) if baseline else None,
            Jsonb(baseline) if baseline else None,
        ),
    )
    return operation


def test_dataset_can_replace_twice_without_duplicate_initial_identity(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline = replacement_dataset(connection)
        first = bulk_operation(connection, workspace, dataset)
        replacements = [
            bulk_operation(connection, workspace, dataset, kind="replace", baseline=baseline)
            for _ in range(2)
        ]
        connection.commit()
        assert connection.execute("SELECT count(*) FROM flyquery_datasets").fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM flyquery_bulk_operations WHERE dataset_id=%s", (dataset,)
        ).fetchone() == (3,)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            bulk_operation(connection, workspace, dataset)
        for statement in (
            "UPDATE flyquery_bulk_operations SET "
            "operation_kind='initial',baseline_json=NULL,baseline_sha256=NULL WHERE id=%s",
            "UPDATE flyquery_bulk_operations SET baseline_json='{}' WHERE id=%s",
        ):
            with pytest.raises(psycopg.Error), connection.transaction():
                connection.execute(statement, (replacements[0],))
        assert connection.execute(
            "SELECT operation_kind,baseline_json FROM flyquery_bulk_operations WHERE id=%s", (first,)
        ).fetchone() == ("initial", None)


@pytest.mark.parametrize(
    "problem",
    ["missing_member", "stale_snapshot", "foreign_dataset", "duplicate_member", "old_file", "wrong_hash"],
)
def test_replacement_rejects_incomplete_or_changed_baseline(metadata_database, problem):
    import copy

    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, original = replacement_dataset(connection)
        baseline = copy.deepcopy(original)
        file_id = None
        if problem == "missing_member":
            baseline["members"] = []
        elif problem == "stale_snapshot":
            baseline["members"][0]["snapshot_id"] = str(uuid4())
        elif problem == "foreign_dataset":
            baseline["dataset_id"] = str(uuid4())
        elif problem == "duplicate_member":
            baseline["members"] *= 2
        elif problem == "old_file":
            file_id = original["native_file_id"]
        elif problem == "wrong_hash":
            baseline["sha256"] = "d" * 64
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            bulk_operation(connection, workspace, dataset, kind="replace", baseline=baseline, file_id=file_id)
        assert connection.execute("SELECT count(*) FROM flyquery_bulk_operations").fetchone() == (0,)


def test_replacement_plan_covers_old_members_and_preserves_retained_ids(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, baseline = replacement_dataset(connection)
        operation = bulk_operation(connection, workspace, dataset, kind="replace", baseline=baseline)
        member = baseline["members"][0]
        valid = {
            "schema": "koinon.dataset-replacement-member.v1",
            "member_key": "root",
            "action": "retain",
            "table_id": member["table_id"],
            "catalog_table_id": member["catalog_table_id"],
            "snapshot_id": str(uuid4()),
        }
        for invalid in (
            [{**valid, "action": "add"}],
            [{**valid, "table_id": str(uuid4())}],
            [{**valid, "snapshot_id": member["snapshot_id"]}],
            [],
            [valid, valid],
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    "UPDATE flyquery_bulk_operations SET plan_json=%s WHERE id=%s",
                    (Jsonb(invalid), operation),
                )
        connection.execute(
            "UPDATE flyquery_bulk_operations SET plan_json=%s WHERE id=%s", (Jsonb([valid]), operation)
        )
        with pytest.raises(psycopg.Error), connection.transaction():
            connection.execute(
                "UPDATE flyquery_bulk_operations SET plan_json=%s WHERE id=%s",
                (Jsonb([{**valid, "member_key": "other"}]), operation),
            )
        assert connection.execute(
            "SELECT plan_json FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == ([valid],)


def test_semantic_history_keeps_exact_parent_version_and_payload(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, _ = replacement_dataset(connection)
        metric, ledger, operation = uuid4(), uuid4(), uuid4()
        connection.execute(
            "INSERT INTO "
            "flyquery_semantic_metrics(id,tenant_id,workspace_id,dataset_id,name,definition"
            "_yaml) VALUES(%s,'tenant',%s,%s,'Revenue','definition')",
            (metric, workspace, dataset),
        )
        connection.execute(
            """INSERT INTO flyquery_metadata_provenance
            (id,tenant_id,workspace_id,entity_kind,entity_id,semantic_version,payload_json,payload_sha256,
             manifest_json,manifest_sha256,created_by,producer_kind,producer_operation_id,producer_ordinal,producer_size,request_sha256)
            SELECT %s,tenant_id,workspace_id,'metric',id,current_version,
              public.koinon_metadata_payload('metric',to_jsonb(t)),
              public.koinon_json_sha256(public.koinon_metadata_payload('metric',to_jsonb(t))),
              m,public.koinon_json_sha256(m),'reader','manual',%s,0,1,repeat('a',64)
            FROM flyquery_semantic_metrics t CROSS JOIN (SELECT
              '{"schema":"koinon.structured-metadata-provenance.v1","complete":true,
                "tables":[],"provenance_ids":[],"query_ids":[]}'::jsonb m) manifest WHERE id=%s""",
            (ledger, operation, metric),
        )
        connection.execute(
            "UPDATE flyquery_semantic_metrics SET source_provenance_id=%s WHERE id=%s", (ledger, metric)
        )
        for version, definition in ((2, "definition"), (1, "forged")):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO "
                    "flyquery_semantic_versions(id,tenant_id,workspace_id,kind,parent_id,version,de"
                    "finition_yaml,created_by,source_provenance_id) "
                    "VALUES(%s,'tenant',%s,'METRIC',%s,%s,%s,'reader',%s)",
                    (uuid4(), workspace, metric, version, definition, ledger),
                )
        version_id = uuid4()
        connection.execute(
            "INSERT INTO "
            "flyquery_semantic_versions(id,tenant_id,workspace_id,kind,parent_id,version,de"
            "finition_yaml,created_by,source_provenance_id) "
            "VALUES(%s,'tenant',%s,'METRIC',%s,1,'definition','reader',%s)",
            (version_id, workspace, metric, ledger),
        )
        connection.commit()
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="historical metadata"),
            connection.transaction(),
        ):
            connection.execute(
                "UPDATE flyquery_semantic_versions SET created_by='another' WHERE id=%s", (version_id,)
            )
        assert connection.execute(
            "SELECT parent_id,version,definition_yaml,source_provenance_id FROM "
            "flyquery_semantic_versions WHERE id=%s",
            (version_id,),
        ).fetchone() == (metric, 1, "definition", ledger)


def test_forward_migrations_preserve_legacy_metadata_without_invented_provenance(source_database):
    target, _, engine = source_database
    with engine.connect() as connection:
        config = _fixture.load("deploy/migrate.py").history_config(
            "structured", ROOT / "packages/structured/migrations/versions", connection
        )
        command.upgrade(config, "0020_bulk_query_operations")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        entity, workspace = glossary(connection)
        query = published_query(connection)
        before = connection.execute(
            "SELECT to_jsonb(t) FROM flyquery_glossary_terms t WHERE id=%s", (entity,)
        ).fetchone()[0]
        query_before = connection.execute(
            "SELECT to_jsonb(t) FROM flyquery_queries t WHERE id=%s", (query,)
        ).fetchone()[0]
    with engine.connect() as connection:
        config = _fixture.load("deploy/migrate.py").history_config(
            "structured", ROOT / "packages/structured/migrations/versions", connection
        )
        command.upgrade(config, "head")
        connection.commit()
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT to_jsonb(t)-'source_provenance_id',source_provenance_id FROM "
            "flyquery_glossary_terms t WHERE id=%s",
            (entity,),
        ).fetchone() == (before, None)
        assert connection.execute(
            "SELECT to_jsonb(t) FROM flyquery_queries t WHERE id=%s", (query,)
        ).fetchone() == (query_before,)
        assert connection.execute("SELECT count(*) FROM flyquery_metadata_provenance").fetchone() == (0,)
        assert connection.execute("SELECT version_num FROM koinon_structured_version").fetchone() == (
            ScriptDirectory.from_config(config).get_current_head(),
        )
        assert connection.execute("SELECT version_num FROM koinon_native_version").fetchone() == (
            "koinon_0044_knowledge_modes",
        )


@pytest.mark.parametrize("interruption", ["first_index", "later_index", "validation"])
def test_index_migration_resumes_from_versioned_expansion(source_database, interruption):
    from sqlalchemy import event

    target, _, engine = source_database
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    migrate = _fixture.load("deploy/migrate.py")
    versions = ROOT / "packages/structured/migrations/versions"
    with engine.connect() as connection:
        command.upgrade(
            migrate.history_config("structured", versions, connection), "0022_dataset_replacement"
        )
        connection.commit()
    with psycopg.connect(uri) as connection:
        entity, _ = glossary(connection)
    needle = {
        "first_index": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_flyquery_relations",
        "later_index": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_flyquery_examples",
        "validation": "ALTER TABLE flyquery_semantic_dimensions VALIDATE",
    }[interruption]

    def interrupt(connection, cursor, statement, parameters, context, executemany):
        if needle in statement:
            raise RuntimeError("owned migration interruption")

    with engine.connect() as connection:
        event.listen(connection, "before_cursor_execute", interrupt)
        try:
            with pytest.raises(RuntimeError, match="owned migration interruption"):
                command.upgrade(migrate.history_config("structured", versions, connection), "head")
        finally:
            event.remove(connection, "before_cursor_execute", interrupt)
            connection.rollback()
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT version_num FROM koinon_structured_version").fetchone() == (
            "0022_dataset_replacement",
        )
        assert connection.execute(
            "SELECT definition,source_provenance_id FROM flyquery_glossary_terms WHERE id=%s", (entity,)
        ).fetchone() == ("Definition", None)
    with engine.connect() as connection:
        config = migrate.history_config("structured", versions, connection)
        command.upgrade(config, "head")
        connection.commit()
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT version_num FROM koinon_structured_version").fetchone() == (
            ScriptDirectory.from_config(config).get_current_head(),
        )
        assert connection.execute(
            "SELECT count(*) FROM pg_constraint WHERE conname LIKE "
            "'fk_flyquery_%_source_provenance' AND convalidated"
        ).fetchone() == (6,)


def test_concurrent_index_failure_is_rebuilt_without_losing_legacy_rows(source_database):
    target, _, engine = source_database
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    migrate = _fixture.load("deploy/migrate.py")
    versions = ROOT / "packages/structured/migrations/versions"
    with engine.connect() as connection:
        command.upgrade(
            migrate.history_config("structured", versions, connection), "0022_dataset_replacement"
        )
        connection.commit()
    with psycopg.connect(uri) as connection:
        entity, _ = glossary(connection)
    with psycopg.connect(uri, autocommit=True) as connection:
        with pytest.raises(psycopg.errors.DivisionByZero):
            connection.execute(
                "CREATE INDEX CONCURRENTLY ix_flyquery_glossary_terms_source_provenance ON "
                "flyquery_glossary_terms ((1/(length(term)-length(term))))"
            )
        assert connection.execute(
            "SELECT indisvalid FROM pg_index WHERE "
            "indexrelid='ix_flyquery_glossary_terms_source_provenance'::regclass"
        ).fetchone() == (False,)
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("structured", versions, connection), "head")
        connection.commit()
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT indisvalid,pg_get_indexdef(indexrelid,1,true) FROM pg_index WHERE "
            "indexrelid='ix_flyquery_glossary_terms_source_provenance'::regclass"
        ).fetchone() == (True, "source_provenance_id")
        assert connection.execute(
            "SELECT definition FROM flyquery_glossary_terms WHERE id=%s", (entity,)
        ).fetchone() == ("Definition",)

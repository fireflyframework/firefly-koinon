# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual native43-to44 history and runtime privilege proof in a retained owned database."""

import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native44_preserves_policy_and_runtime_cannot_forge_generation(record_property):
    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port not in (None, 18783)
    suffix = uuid4().hex[:12]
    database, role = "mode_migration_" + suffix, "mode_runtime_" + suffix
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database))
        )
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(
                sql.Identifier(role)
            )
        )
    record_property("owned_database", database)
    record_property("owned_runtime_role", role)
    target = base.set(database=database)
    engine = create_engine(target.set(drivername="postgresql+psycopg"))
    migrate = load("mode_history", "deploy/migrate.py")
    roles = load("mode_roles", "deploy/provision_roles.py")
    try:
        with engine.connect() as connection:
            config = migrate.history_config("native", ROOT / "deploy/migrations/native_versions", connection)
            command.upgrade(config, "koinon_0043_ordinary_folders")
            connection.commit()
            connection.exec_driver_sql(
                "INSERT INTO lattice_tenants(id,name,created_at) VALUES('retained','Retained',now())"
            )
            policy = json.loads((ROOT / "sdk/contract/fixtures.json").read_text())["fixtures"][
                "OrganizationKnowledgeSettingsInput"
            ]
            connection.exec_driver_sql(
                "INSERT INTO koinon_organization_knowledge_settings(tenant_id,schema_version,revision,"
                "documents,structured,updated_by,updated_at) "
                "VALUES('retained',1,7,%s::json,%s::json,'admin',now())",
                (json.dumps(policy["documents"]), json.dumps(policy["structured"])),
            )
            before = connection.exec_driver_sql(
                "SELECT to_jsonb(s)::text FROM koinon_organization_knowledge_settings s"
            ).all()
            connection.commit()
            command.upgrade(config, "koinon_0044_knowledge_modes")
            connection.commit()
            assert (
                connection.exec_driver_sql(
                    "SELECT to_jsonb(s)::text FROM koinon_organization_knowledge_settings s"
                ).all()
                == before
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT generation FROM koinon_knowledge_readiness_generations WHERE tenant_id='retained'"
                ).scalar_one()
                == 0
            )
            assert (
                connection.exec_driver_sql(
                    "SELECT count(*) FROM koinon_knowledge_mode_transitions"
                ).scalar_one()
                == 0
            )
            assert (
                connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one()
                == "koinon_0044_knowledge_modes"
            )
        from koinon.jobs.entities import Job
        from koinon.organization_knowledge.transitions.entities import (
            KnowledgeModeIndexAttempt,
            KnowledgeModeIndexResolution,
            KnowledgeModeTransition,
        )

        with engine.begin() as connection:
            connection.execute(
                Job.__table__.insert().values(
                    id="mode-job",
                    tenant_id="retained",
                    resource_id="retained",
                    kind="knowledge.mode",
                    idempotency_key="attempt-proof",
                    payload_hash="a" * 64,
                )
            )
            connection.execute(
                KnowledgeModeTransition.__table__.insert().values(
                    id="mode",
                    tenant_id="retained",
                    job_id="mode-job",
                    actor="admin",
                    base_revision=7,
                    base_digest="a" * 64,
                    active_mode="rag",
                    requested_settings=policy,
                )
            )
            connection.execute(
                KnowledgeModeIndexAttempt.__table__.insert().values(
                    id="attempt",
                    tenant_id="retained",
                    transition_id="mode",
                    index_id="index",
                    attempt_revision=3,
                    workspace_id="original-workspace",
                    native_workspace_id="original-native",
                    native_id="original-set",
                    provider_id="provider",
                    provider_revision=1,
                    model_id="embedding",
                    dimensions=768,
                    storage_dimensions=768,
                    embedding_fingerprint="fingerprint",
                    actor="admin",
                    request={"expected_revision": 2},
                )
            )
            connection.execute(
                KnowledgeModeIndexResolution.__table__.insert().values(id="attempt", tenant_id="retained")
            )
        owner_uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
        with psycopg.connect(owner_uri) as owner:
            owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
            for table in (
                "koinon_knowledge_readiness_generations",
                "koinon_knowledge_readiness_changes",
                "koinon_knowledge_readiness_pending",
                "koinon_knowledge_mode_index_attempts",
                "koinon_knowledge_mode_index_resolutions",
            ):
                roles.grant_table(owner, table, role)
        with psycopg.connect(owner_uri, autocommit=True) as owner:
            for statement in (
                "UPDATE koinon_knowledge_mode_index_attempts SET native_workspace_id='forged' "
                "WHERE id='attempt'",
                "DELETE FROM koinon_knowledge_mode_index_attempts",
                "TRUNCATE koinon_knowledge_mode_index_attempts CASCADE",
                "UPDATE koinon_knowledge_mode_index_resolutions SET status='finished' WHERE id='attempt'",
            ):
                with pytest.raises(psycopg.errors.CheckViolation):
                    owner.execute(statement)
        runtime = target.set(drivername="postgresql", username=role, password=None).render_as_string(
            hide_password=False
        )
        with psycopg.connect(runtime, autocommit=True) as caller:
            assert caller.execute("SELECT koinon_lock_knowledge_readiness('retained',0)").fetchone() == (
                True,
            )
            assert caller.execute(
                "SELECT native_workspace_id FROM koinon_knowledge_mode_index_attempts WHERE id='attempt'"
            ).fetchone() == ("original-native",)
            assert caller.execute(
                "UPDATE koinon_knowledge_mode_index_resolutions "
                "SET status='restored',revision=2,updated_at=now() "
                "WHERE id='attempt' AND revision=1 RETURNING id"
            ).fetchone() == ("attempt",)
            with pytest.raises(psycopg.errors.CheckViolation):
                caller.execute(
                    "UPDATE koinon_knowledge_mode_index_resolutions "
                    "SET status='finished',revision=3,updated_at=now() WHERE id='attempt'"
                )
            for statement in (
                "UPDATE koinon_knowledge_mode_index_attempts SET native_workspace_id='forged'",
                "DELETE FROM koinon_knowledge_mode_index_attempts",
                "TRUNCATE koinon_knowledge_mode_index_attempts",
                "UPDATE koinon_knowledge_mode_index_resolutions SET tenant_id='foreign'",
                "DELETE FROM koinon_knowledge_mode_index_resolutions",
                "UPDATE koinon_knowledge_readiness_generations SET generation=900 WHERE tenant_id='retained'",
                "DELETE FROM koinon_knowledge_readiness_generations",
                "UPDATE koinon_knowledge_readiness_changes SET generation=900",
                "SELECT * FROM koinon_knowledge_readiness_pending",
                "TRUNCATE koinon_knowledge_readiness_generations",
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    caller.execute(statement)
    finally:
        engine.dispose()
    # Database and role are retained for independent inspection.

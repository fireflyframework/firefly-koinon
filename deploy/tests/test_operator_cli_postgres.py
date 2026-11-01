# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Complete native CLI flow under a dedicated nonowner PostgreSQL operator identity."""

import base64
import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from koinon.app import create_application
from koinon.bootstrap.dtos import BootstrapSeedInput
from koinon.bootstrap.service import BootstrapGrants
from koinon.communications.contact_dtos import OperatorContactInput
from psycopg import sql
from pyfly.data.transaction.registry import TransactionManagerRegistry, bind_registry
from pyfly.security.context import SecurityContext
from sqlalchemy.engine import make_url
from starlette.requests import Request

ROOT = Path(__file__).parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


cli = load(ROOT / "communications.py", "native_contacts_cli")
roles = load(ROOT / "provision_roles.py", "native_contacts_roles")
TID = "00000000-0000-4000-8000-000000000011"
OID = "00000000-0000-4000-8000-000000000012"
ISSUER = f"https://login.microsoftonline.com/{TID}/v2.0"


def configuration(url, ddl):
    return {
        "pyfly": {
            "banner": {"mode": "off"},
            "data": {"relational": {"enabled": True, "ddl-auto": ddl, "url": url}},
            "notifications": {
                "enabled": True,
                "email": {"provider": "smtp", "smtp": {"host": "127.0.0.1", "port": 1}},
            },
        },
        "koinon": {
            "public_url": "https://knowledge.example.test",
            "knowledge": {"enabled": False},
            "identity": {"master_key": base64.urlsafe_b64encode(b"q" * 32).decode()},
            "security": {
                "issuer": ISSUER,
                "client_id": "client",
                "api_audience": "api",
                "jwks_uri": ISSUER + "/keys",
                "authorization_uri": ISSUER + "/authorize",
                "token_uri": ISSUER + "/token",
                "redirect_uri": "https://knowledge.example.test/login/oauth2/code/koinon",
            },
            "communications": {
                "enabled": True,
                "verified_senders": [
                    {
                        "id": "main",
                        "display_name": "Knowledge team",
                        "address": "team@example.test",
                    }
                ],
            },
        },
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_postgres_cli_provisions_durable_contact_and_queues_diagnostic_with_minimal_role():
    uri = os.environ.get("KOINON_CONTACT_TEST_PG_URL") or os.environ.get(
        "KOINON_INSTALLATION_ANN_TEST_PG_URL"
    )
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port not in {None, 18783}
    suffix = uuid4().hex[:12]
    database, operator = "contact_cli_" + suffix, "contact_cli_op_" + suffix
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
        )
        connection.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(operator))
        )
    target = base.set(database=database)
    owner_url = target.set(drivername="postgresql+asyncpg").render_as_string(
        hide_password=False
    )
    owner = create_application(
        configuration(owner_url, "create"), role="api"
    ).state.context
    await owner.start()
    try:
        with bind_registry(owner.get_bean(TransactionManagerRegistry)):
            bootstrap = owner.get_bean(BootstrapGrants)
            await bootstrap.seed(
                "north",
                "North",
                BootstrapSeedInput.model_validate(
                    {
                        "issuer": ISSUER,
                        "client_id": "client",
                        "entra_tenant_id": TID,
                        "grants": [
                            {
                                "object_id": OID,
                                "role": "admin",
                                "expires_at": datetime.now(UTC) + timedelta(hours=4),
                            }
                        ],
                    }
                ),
            )
            await bootstrap.observe_login(
                Request(
                    {
                        "type": "http",
                        "method": "GET",
                        "path": "/login/oauth2/code/koinon",
                        "headers": [],
                    }
                ),
                SimpleNamespace(
                    client_id="client",
                    issuer_uri=ISSUER,
                    redirect_uri="https://knowledge.example.test/login/oauth2/code/koinon",
                ),
                SecurityContext(
                    user_id="actual-pairwise-sub",
                    attributes={
                        "iss": ISSUER,
                        "sub": "actual-pairwise-sub",
                        "aud": "client",
                        "azp": "client",
                        "tid": TID,
                        "oid": OID,
                    },
                ),
            )
    finally:
        await owner.stop()
    with psycopg.connect(
        target.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
    ) as connection:
        connection.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), sql.Identifier(operator)
            )
        )
        connection.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(operator)
            )
        )
        roles.grant_contact_operator(connection, operator)
        roles.check_contact_operator(connection, operator)
        connection.execute(
            sql.SQL("GRANT UPDATE(subject) ON lattice_memberships TO {}").format(
                sql.Identifier(operator)
            )
        )
        with pytest.raises(RuntimeError, match="column"):
            roles.check_contact_operator(connection, operator)
        connection.execute(
            sql.SQL("REVOKE UPDATE(subject) ON lattice_memberships FROM {}").format(
                sql.Identifier(operator)
            )
        )
        roles.check_contact_operator(connection, operator)
        assert connection.execute(
            "SELECT has_table_privilege(%s,'public.lattice_memberships','UPDATE'),has_table_privilege(%s,'public.koinon_communication_outbox','UPDATE'),has_column_privilege(%s,'public.koinon_operator_delivery_contacts','canonical_subject','UPDATE')",
            (operator,) * 3,
        ).fetchone() == (False, False, False)
    operator_url = target.set(
        drivername="postgresql+asyncpg", username=operator
    ).render_as_string(hide_password=False)
    context = create_application(
        configuration(operator_url, "validate"), role="api"
    ).state.context
    await context.start()
    try:
        now = datetime.now(UTC)
        value = OperatorContactInput.model_validate(
            {
                "tenant_id": "north",
                "identity": {
                    "kind": "entra",
                    "issuer": ISSUER,
                    "client_id": "client",
                    "external_tenant_id": TID,
                    "external_subject": OID,
                },
                "email": "approved@example.test",
                "display_name": "Approved administrator",
                "source": "microsoft_graph_v1",
                "account_enabled": None,
                "observed_at": now,
                "expires_at": now + timedelta(days=365),
            }
        )
        admitted = await cli.execute(
            context,
            cli.arguments(["provision", "--contacts-file", "protected.json"]),
            [value],
        )
        identifier = admitted["contacts"][0]["contact_id"]
        status = await cli.execute(
            context, cli.arguments(["status", "--contact-id", identifier])
        )
        assert (
            status["recipient_state"] == "eligible"
            and status["expiry_state"] == "current"
        )
        operation = str(uuid4())
        arguments = cli.arguments(
            ["diagnostic", "--contact-id", identifier, "--operation-id", operation]
        )
        result = await cli.execute(context, arguments)
        assert result["status"] == "queued"
        assert await cli.execute(context, arguments) == result
        with psycopg.connect(
            target.set(drivername="postgresql", username=operator).render_as_string(
                hide_password=False
            )
        ) as connection:
            row = connection.execute(
                "SELECT owner_subject,attempt_count,status FROM koinon_communication_outbox WHERE id=%s",
                (result["delivery_id"],),
            ).fetchone()
            assert row == (ISSUER + "|actual-pairwise-sub", 0, "queued")
            assert (
                connection.execute(
                    "SELECT count(*) FROM lattice_audit WHERE subject='system:communications-operator'"
                ).fetchone()[0]
                == 2
            )
    finally:
        await context.stop()
    # Databases and roles are retained. No SMTP connection or actual provider send occurs.

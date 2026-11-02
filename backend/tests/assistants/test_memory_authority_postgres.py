# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual PostgreSQL memory observations retain JSON application authority once per ID."""

import base64
import json
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import update
from sqlalchemy.engine import make_url
from test_service import configured

from koinon.assistants.memory.authority_repository import ChatMemoryAuthorityRepository
from koinon.assistants.memory.projections import MemoryCurrentEvidence
from koinon.authorized_applications.entities import AuthorizedApplication
from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.tokens.entities import PersonalToken

pytestmark = pytest.mark.integration


@pytest.fixture
async def pg_assistants():
    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings
    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    import koinon.jobs.entities  # noqa: F401
    from koinon.assistants.service import AssistantService

    uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    url = make_url(uri)
    assert url.host == "127.0.0.1" and url.port != 18783
    database = "memory_authority_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    url = url.set(drivername="postgresql+asyncpg", database=database)
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "scheduling": {"enabled": False},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                    "data": {"relational": {"enabled": True, "ddl-auto": "create", "url": str(url)}},
                },
                "koinon": {
                    "assistants": {
                        "master_key": base64.urlsafe_b64encode(b"k" * 32).decode(),
                        "allowed_provider_hosts": ["127.0.0.1", "models.example.test"],
                    }
                },
            }
        )
    )
    context.container.register_instance(CanonSettings, CanonSettings(answer_mode="rag"))
    context.container.register_instance(FlyquerySettings, FlyquerySettings())
    for package in (
        "koinon.catalog",
        "koinon.organization_knowledge",
        "koinon.organization_branding",
        "koinon.assistants",
    ):
        scan_package(package, context.container)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant.title()))
        await context.get_bean(MembershipRepository).save(
            Membership(id="admin", subject="issuer|admin", tenant_id="north", role="admin")
        )
        yield (
            context.get_bean(AssistantService),
            context,
            context.get_bean(DataSourceRegistry).session_factory(),
        )
    finally:
        await context.stop()


async def test_postgres_first_queued_message_page_needs_no_application(pg_assistants):
    service, _, _ = pg_assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|admin", "north", {"title": "First conversation"})
    assert await service.messages("issuer|admin", "north", thread["id"]) == []
    await service.submit(
        "issuer|admin",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "A synthetic question", "client_request_id": "first"},
    )
    messages = await service.messages("issuer|admin", "north", thread["id"])
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["text"] == "A synthetic question"
    assert messages[1]["status"] == "queued"


async def test_postgres_application_json_is_deduplicated_with_exact_authority_filters(
    pg_assistants, monkeypatch
):
    import koinon.assistants.memory.authority_repository as authority

    _, context, factory = pg_assistants
    now = datetime.now(UTC)
    apps, tokens = [], []
    for identifier, subject, tenant, revoked, expired in (
        ("live", "issuer|admin", "north", False, False),
        ("revoked", "issuer|admin", "north", True, False),
        ("expired", "issuer|admin", "north", False, True),
        ("foreign-subject", "issuer|other", "north", False, False),
        ("foreign-tenant", "issuer|admin", "south", False, False),
        ("no-live-token", "issuer|admin", "north", False, False),
    ):
        apps.append(
            AuthorizedApplication(
                id=identifier,
                subject=subject,
                tenant_id=tenant,
                client_id="client-" + identifier,
                name=identifier,
                resource="https://resource.example.test/mcp",
                tenant_name=tenant,
                workspace_id="workspace",
                workspace_name="Research",
                scopes=["assistants:read"],
                client_registration={"nested": {"enabled": True}, "redirects": ["https://client.test"]},
                connected_at=now,
                expires_at=now + timedelta(hours=-1 if expired else 1),
                revoked_at=now if revoked else None,
            )
        )
        for suffix in ("a", "b"):
            tokens.append(
                PersonalToken(
                    id=identifier + suffix,
                    subject=subject,
                    tenant_id=tenant,
                    purpose="application",
                    authorized_application_id=identifier,
                    name="Synthetic",
                    token_hash="0" * 64,
                    prefix="unused",
                    scopes=["assistants:read"],
                    workspace_ids=["workspace"],
                    asset_ids=None,
                    resource_ids=["resource"],
                    expires_at=now
                    + timedelta(hours=-1 if identifier == "no-live-token" and suffix == "b" else 1),
                    revoked_at=now if identifier == "no-live-token" and suffix == "a" else None,
                )
            )
    async with factory() as session, session.begin():
        session.add_all(apps)
        await session.flush()
        session.add_all(tokens)
    seen = []
    original = authority.partition_material

    def capture(rows, *args):
        seen.extend(rows)
        return original(rows, *args)

    monkeypatch.setattr(authority, "partition_material", capture)
    evidence = MemoryCurrentEvidence("run", "thread", "issuer|admin", "north", {}, "livea", (), ())
    repository = context.get_bean(ChatMemoryAuthorityRepository)
    before = await repository.observe_many(
        (),
        Membership.__table__,
        None,
        "deployment",
        (evidence,),
        additional_token_ids=tuple(token.id for token in tokens),
    )
    applications = [row for row in seen if row[0] == "application"]
    assert [row[1] for row in applications] == ["live"]
    assert json.loads(applications[0][6]) == ["assistants:read"]
    assert json.loads(applications[0][8]) == {
        "nested": {"enabled": True},
        "redirects": ["https://client.test"],
    }
    assert {row[1] for row in seen if row[0] == "token"} == {
        "livea",
        "liveb",
        "revokeda",
        "revokedb",
        "expireda",
        "expiredb",
    }
    async with factory() as session, session.begin():
        await session.execute(
            update(AuthorizedApplication).where(AuthorizedApplication.id == "live").values(revoked_at=now)
        )
    seen.clear()
    after = await repository.observe_many(
        (),
        Membership.__table__,
        None,
        "deployment",
        (evidence,),
        additional_token_ids=tuple(token.id for token in tokens),
    )
    assert not [row for row in seen if row[0] == "application"]
    assert before["__current__"].current_sha256 != after["__current__"].current_sha256

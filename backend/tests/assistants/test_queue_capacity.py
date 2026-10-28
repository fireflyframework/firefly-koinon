# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException
from test_service import assistants as assistants
from test_service import configured


async def test_capacity_applies_across_threads_and_retries_without_blocking_idempotent_replay(assistants):
    service, _ = assistants
    service.operations.max_queued_per_subject = 1
    _, agent = await configured(service)
    subject, tenant = "issuer|viewer", "north"
    first = await service.create_thread(subject, tenant, {"title": "First"})
    second = await service.create_thread(subject, tenant, {"title": "Second"})
    payload = {"agent_id": agent["id"], "message": "Find the source", "client_request_id": "capacity"}
    accepted = await service.submit(subject, tenant, first["id"], payload)
    assert await service.submit(subject, tenant, first["id"], payload) == accepted
    with pytest.raises(ConflictException, match="queue"):
        await service.submit(subject, tenant, second["id"], payload)
    assert await service.messages(subject, tenant, second["id"]) == []
    await service.cancel(subject, tenant, accepted["run_id"])
    next_run = await service.submit(subject, tenant, second["id"], payload)
    with pytest.raises(ConflictException, match="queue"):
        await service.retry(subject, tenant, accepted["run_id"])
    assert (await service.owned_run(subject, tenant, accepted["run_id"])).status == "cancelled"
    await service.cancel(subject, tenant, next_run["run_id"])
    assert (await service.retry(subject, tenant, accepted["run_id"]))["status"] == "queued"


@pytest.mark.integration
async def test_postgres_concurrent_owner_admission_is_serialized_across_threads(monkeypatch):
    import asyncio
    import os
    from contextlib import suppress
    from uuid import uuid4

    from pyfly.container.scanner import scan_package
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.relational.sqlalchemy import SessionProvider
    from sqlalchemy.engine import make_url

    from koinon.assistants.repositories import ChatRunRepository
    from koinon.assistants.service import AssistantService
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import MembershipRepository, TenantRepository

    url = os.environ.get("KOINON_REVIEW_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured owned restore database")
    target = make_url(url)
    assert target.database.startswith("koinon_restore_")
    assert target.host == "127.0.0.1" and target.port == 18783
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "agentic": {"enabled": True},
                    "data": {"relational": {"enabled": True, "ddl-auto": "validate", "url": url}},
                },
                "koinon": {
                    "assistants": {"allowed_provider_hosts": ["127.0.0.1"]},
                    "operations": {"max_queued_per_subject": 1},
                },
            }
        )
    )
    for package in ("koinon.catalog", "koinon.assistants", "koinon.operations"):
        scan_package(package, context.container)
    await context.start()
    try:
        tenant, subject = "cap-" + uuid4().hex, "queue-review|" + uuid4().hex
        await context.get_bean(TenantRepository).save(Tenant(id=tenant, name="Owned queue admission review"))
        await context.get_bean(MembershipRepository).save(
            Membership(id=str(uuid4()), subject=subject, tenant_id=tenant, role="admin")
        )
        service = context.get_bean(AssistantService)
        provider = await service.save_provider(
            subject,
            tenant,
            {
                "name": "No-call local fixture",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["fixture"],
            },
        )
        agent = await service.save_agent(
            subject, tenant, {"name": "No-call agent", "provider_id": provider["id"], "model_id": "fixture"}
        )
        threads = [await service.create_thread(subject, tenant, {"title": title}) for title in ("One", "Two")]
        original = ChatRunRepository.count_active_for_subject
        both_reads, reads = asyncio.Event(), []

        async def barrier(self, tenant_id, owner):
            count = await original(self, tenant_id, owner)
            if tenant_id == tenant and owner == subject:
                reads.append(count)
                if len(reads) == 2:
                    both_reads.set()
                with suppress(TimeoutError):
                    await asyncio.wait_for(both_reads.wait(), 0.5)
            return count

        monkeypatch.setattr(ChatRunRepository, "count_active_for_subject", barrier)
        payload = {
            "agent_id": agent["id"],
            "message": "Admission only; no model call",
            "client_request_id": "bounded-cap-review",
        }
        results = await asyncio.wait_for(
            asyncio.gather(
                *(service.submit(subject, tenant, thread["id"], payload) for thread in threads),
                return_exceptions=True,
            ),
            10,
        )
        assert reads == [0, 1], "The second count must follow the first transaction's committed admission"
        accepted = [result for result in results if isinstance(result, dict)]
        denied = [result for result in results if isinstance(result, ConflictException)]
        assert len(accepted) == len(denied) == 1, results
        assert denied[0].code == "QUEUE_LIMIT_REACHED"
        async with context.get_bean(SessionProvider).unit(read_only=True):
            assert await original(service.runs, tenant, subject) == 1
        histories = [await service.messages(subject, tenant, thread["id"]) for thread in threads]
        assert sum(map(len, histories)) == 2
    finally:
        await context.stop()

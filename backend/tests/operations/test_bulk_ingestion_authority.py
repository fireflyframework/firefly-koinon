# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A bulk child's saved origin must reach the actual native ingestion policy."""

import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from test_worker_execution_authority import captured as captured
from test_worker_execution_authority import client as client
from test_worker_execution_authority import knowledge_core as knowledge_core

from koinon.knowledge.bulk.execution import BulkExecutor
from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation
from koinon.knowledge.bulk.queue import BulkOriginal, BulkQueue
from koinon.knowledge.connections.entities import KnowledgeConnection
from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.repositories import DomainBindingRepository


@pytest.mark.parametrize("cancelled", [False, True])
@pytest.mark.parametrize("domain", ["canon", "structured"])
@pytest.mark.parametrize("pinned", [False, True])
@pytest.mark.parametrize("credential", [False, True])
def test_bulk_origin_reaches_real_ingestion_capture_without_borrowing_ambient_identity(
    client, captured, domain, pinned, credential, cancelled
):
    authority, value, security = captured

    async def exercise():
        context = client.native_app.state.context
        if domain == "canon":
            await context.get_bean(DomainBindingRepository).save(
                DomainBinding(
                    id="canon-workspace-binding",
                    tenant_id=value.tenant_id,
                    catalog_id=value.catalog_workspace_id,
                    workspace_id=value.catalog_workspace_id,
                    domain="canon",
                    entity_kind="workspace",
                    native_id=value.native_workspace_id,
                    native_workspace_id=value.native_workspace_id,
                    created_by=value.subject,
                )
            )
            await context.get_bean(KnowledgeConnectionRepository).save(
                KnowledgeConnection(
                    id="document-assignment",
                    tenant_id=value.tenant_id,
                    workspace_id=value.catalog_workspace_id,
                    scope_key=value.catalog_workspace_id,
                    domain="documents",
                    role="documents.embedding",
                    mode="provider",
                    provider_id="provider",
                    model_id="declared-model",
                    dimensions=1536,
                    storage_dimensions=1536,
                    embedding_fingerprint="f" * 64,
                    created_by=value.subject,
                    updated_by=value.subject,
                )
            )
        arguments = dict(
            actor=value.subject,
            tenant_id=value.tenant_id,
            workspace_id=value.native_workspace_id,
            catalog_workspace_id=value.catalog_workspace_id,
            source_catalog_id=value.resource_ids[-1],
        )
        attributes = dict(security.attributes)
        if not credential:
            attributes.pop("koinon_token_id")
        with SecurityContextHolder.using(SecurityContext(user_id="admin", attributes=attributes)):
            origin = await authority.capture(
                domain, arguments, ("documents.embedding",) if domain == "canon" else value.roles
            )
        content = b"controlled-original"
        lease = SimpleNamespace(
            subject=origin.subject,
            token_id=origin.token_id,
            sha256=sha256(content).hexdigest(),
            size_bytes=len(content),
        )
        receipt = NativeCommit(
            domain=domain,
            native_workspace_id=origin.native_workspace_id,
            native_source_id="native",
            native_asset_id="native",
            sha256=lease.sha256,
            size_bytes=lease.size_bytes,
            source_version_id="version",
            extraction_id="extraction",
        )
        observed = []

        async def native_effect(*args):
            await authority.validate(origin)
            assert await authority.capture(domain, arguments, origin.roles) == origin
            observed.append(dict(SecurityContextHolder.get_context().attributes))
            if cancelled:
                raise asyncio.CancelledError
            return receipt

        native = SimpleNamespace(
            reserve=AsyncMock(),
            inspect=AsyncMock(return_value=NativeObservation("absent")),
            execute=AsyncMock(side_effect=native_effect),
            execute_file=AsyncMock(side_effect=native_effect),
            acknowledge=AsyncMock(),
        )
        queue = SimpleNamespace(
            check=AsyncMock(),
            failed=AsyncMock(),
            original=AsyncMock(
                return_value=BulkOriginal(
                    "opaque",
                    len(content),
                    lease.sha256,
                    object_reference_json={"present": True} if pinned else None,
                )
            ),
        )

        async def read_file(original, path):
            path.write_bytes(content)

        storage = SimpleNamespace(
            read=AsyncMock(return_value=content), read_file=AsyncMock(side_effect=read_file)
        )
        executor = BulkExecutor(queue, storage, SimpleNamespace(get=lambda: native))
        ambient = SecurityContext(
            user_id="other",
            attributes={"iss": "unrelated", "sub": "other", "koinon_token_id": "unrelated-token"},
        )
        with SecurityContextHolder.using(ambient):
            if cancelled:
                with pytest.raises(asyncio.CancelledError):
                    await executor.execute(lease)
            else:
                await executor.execute(lease)
            assert SecurityContextHolder.get_context() is ambient
        assert queue.failed.await_count == 0, queue.failed.call_args
        if cancelled:
            native.acknowledge.assert_not_awaited()
        else:
            native.acknowledge.assert_awaited_once_with(lease, receipt)
        assert len(observed) == 1
        assert observed[0]["iss"] + "|" + observed[0]["sub"] == origin.subject
        assert observed[0].get("koinon_token_id") == origin.token_id
        assert SecurityContextHolder.get_context() is None

    client.portal.call(exercise)


@pytest.mark.parametrize("change", ["membership", "credential", "provider", "assignment"])
def test_bulk_reconstructed_origin_still_denies_current_revocation(client, captured, change):
    from koinon.assistants.repositories import ProviderRepository
    from koinon.catalog.repositories import MembershipRepository
    from koinon.tokens.repositories import PersonalTokenRepository

    authority, value, security = captured

    async def exercise():
        context = client.native_app.state.context
        if change == "membership":
            await context.get_bean(MembershipRepository).delete_by_id("admin")
        else:
            kind, identifier, field, replacement = {
                "credential": (PersonalTokenRepository, "credential", "revoked_at", datetime.now(UTC)),
                "provider": (ProviderRepository, "provider", "revision", 2),
                "assignment": (KnowledgeConnectionRepository, "assignment", "revision", 2),
            }[change]
            repository = context.get_bean(kind)
            row = await repository.find_by_id(identifier)
            setattr(row, field, replacement)
            await repository.save(row)
        opened = []

        async def effect(*args):
            await authority.validate(value)
            opened.append(True)
            raise AssertionError("Revoked origin reached native effects")

        lease = SimpleNamespace(subject=value.subject, token_id=value.token_id, sha256="a" * 64, size_bytes=1)
        queue = SimpleNamespace(
            check=AsyncMock(),
            failed=AsyncMock(),
            original=AsyncMock(return_value=BulkOriginal("opaque", 1, "a" * 64)),
        )
        native = SimpleNamespace(
            reserve=AsyncMock(),
            inspect=AsyncMock(return_value=NativeObservation("absent")),
            execute=AsyncMock(side_effect=effect),
            acknowledge=AsyncMock(),
        )
        await BulkExecutor(
            queue, SimpleNamespace(read=AsyncMock(return_value=b"x")), SimpleNamespace(get=lambda: native)
        ).execute(lease)
        assert opened == []
        native.acknowledge.assert_not_awaited()
        queue.failed.assert_awaited_once()
        assert queue.failed.call_args.kwargs["unknown"] is True
        assert queue.failed.call_args.kwargs["code"] in {
            "ACCESS_DENIED",
            "TOKEN_UNAVAILABLE",
            "INGEST_EXECUTION_CONTEXT_REQUIRED",
        }
        assert SecurityContextHolder.get_context() is None

    client.portal.call(exercise)


@pytest.mark.parametrize("subject", [None, "legacy-subject", "|missing-issuer", "missing-subject|", ""])
async def test_unprovable_bulk_origin_fails_closed_before_original_or_native_effect(subject):
    lease = SimpleNamespace(subject=subject, token_id=None)
    queue = SimpleNamespace(check=AsyncMock(), failed=AsyncMock())
    native = SimpleNamespace(get=lambda: pytest.fail("Unprovable origin resolved native intake"))
    await BulkExecutor(queue, None, native).execute(lease)
    queue.check.assert_not_awaited()
    queue.failed.assert_awaited_once_with(lease, code="INGEST_EXECUTION_CONTEXT_REQUIRED", unknown=True)
    assert SecurityContextHolder.get_context() is None


@pytest.mark.parametrize("credential", [False, True])
def test_queue_recheck_preserves_origin_for_actual_native_policy(client, captured, credential):
    authority, value, security = captured

    async def exercise():
        attributes = dict(security.attributes)
        if not credential:
            attributes.pop("koinon_token_id")
        arguments = dict(
            actor=value.subject,
            tenant_id=value.tenant_id,
            workspace_id=value.native_workspace_id,
            catalog_workspace_id=value.catalog_workspace_id,
            source_catalog_id=value.resource_ids[-1],
        )
        with SecurityContextHolder.using(SecurityContext(user_id="admin", attributes=attributes)):
            origin = await authority.capture("structured", arguments, value.roles)

        async def destination(*args, **kwargs):
            await authority.validate(origin)
            assert await authority.capture("structured", arguments, value.roles) == origin

        item = SimpleNamespace(mode="document", connection_json={"pinned": True}, native_workspace_id=None)
        records = SimpleNamespace(
            item=AsyncMock(return_value=item),
            fenced=AsyncMock(
                return_value=(
                    SimpleNamespace(result=None),
                    item,
                    SimpleNamespace(tenant_id="tenant", workspace_id="ws"),
                )
            ),
            connection=AsyncMock(return_value=item.connection_json),
        )
        checker = SimpleNamespace(destination=AsyncMock(side_effect=destination), item=AsyncMock())
        queue = SimpleNamespace(authority=checker, records=records)
        lease = SimpleNamespace(
            subject=origin.subject,
            token_id=origin.token_id,
            tenant_id=origin.tenant_id,
            destination=None,
            source_id="source",
            asset_id="asset",
            sha256="a" * 64,
            batch_id="batch",
            recovery_operation=None,
            item_id="item",
            worker_id="worker",
            attempt=1,
        )
        ambient = SecurityContext(user_id="unrelated", attributes={"iss": "wrong", "sub": "wrong"})
        with SecurityContextHolder.using(ambient):
            await BulkQueue._check(queue, lease)
            assert SecurityContextHolder.get_context() is ambient
        checker.destination.assert_awaited_once()
        assert SecurityContextHolder.get_context() is None

    client.portal.call(exercise)

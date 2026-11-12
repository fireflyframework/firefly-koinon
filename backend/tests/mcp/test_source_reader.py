# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Authenticated capture binds reader choices to one actor and one operation."""

import asyncio
import contextvars
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.transaction import TransactionManagerRegistry
from pyfly.security.context import SecurityContext

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_context import current_reader_choices
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
from koinon.knowledge.external_reviews.read_receipts import ExternalReadReceipts
from koinon.mcp.read_capture import native_read_capture
from koinon.mcp_auth.service import McpOAuthService


def application(native):
    context = ApplicationContext(Config({}))
    context.container.register_instance(TransactionManagerRegistry, TransactionManagerRegistry())

    async def authenticate(token):
        return SecurityContext(user_id=token, attributes={"iss": "issuer", "sub": token})

    context.container.register_instance(McpOAuthService, SimpleNamespace(authenticate=authenticate))
    context.container.register_instance(NativeKnowledgeEvidence, native)
    context.container.register_instance(SourceReader, SimpleNamespace(begin=AsyncMock()))
    receipts = SimpleNamespace(record=AsyncMock(return_value={"status": "not_recorded"}))
    context.container.register_instance(ExternalReadReceipts, receipts)
    return context, receipts


async def test_concurrent_capture_keeps_reader_subject_and_choices_isolated_and_expires_children():
    rendezvous = asyncio.Barrier(2)
    inherited = []

    async def search(actor, tenant, **arguments):
        before = current_reader_choices(actor, tenant)
        inherited.append((contextvars.copy_context(), actor))
        await rendezvous.wait()
        assert current_reader_choices(actor, tenant) == before
        with pytest.raises(SourceError, match="access_denied"):
            current_reader_choices("issuer|other", tenant)
        assert "reader_source_connections" not in arguments
        return CapturedEvidence(
            {"actor": actor, "choices": None if before is None else [x.connection_id for x in before]},
            (),
            False,
        )

    context, _ = application(SimpleNamespace(search=search))
    capture = native_read_capture(context)
    first, second = await asyncio.gather(
        capture("alice", "north", "search", {"question": "Q", "reader_source_connections": []}),
        capture("bob", "north", "search", {"question": "Q"}),
    )
    assert first["actor"] == "issuer|alice" and first["choices"] == []
    assert second["actor"] == "issuer|bob" and second["choices"] is None
    assert current_reader_choices("issuer|alice", "north") is None
    for copied, actor in inherited:
        with pytest.raises(SourceError, match="access_denied"):
            copied.run(current_reader_choices, actor, "north")


async def test_source_denial_does_not_record_receipt_or_disclose_provider_details():
    async def search(actor, tenant, **arguments):
        raise SourceError("access_denied")

    context, receipts = application(SimpleNamespace(search=search))
    with pytest.raises(ToolError, match="Source read is unavailable"):
        await native_read_capture(context)(
            "bob", "north", "search", {"question": "Q", "reader_source_connections": []}
        )
    receipts.record.assert_not_awaited()


async def test_other_users_connection_denied_before_native_schema_read():
    schema = AsyncMock(return_value=CapturedEvidence({"tables": [{"name": "private"}]}, (), False))
    context, receipts = application(SimpleNamespace(schema=schema))

    async def begin(actor, tenant):
        choices = current_reader_choices(actor, tenant)
        assert choices[0].connection_id == "alice-connection"
        if actor != "issuer|alice":
            raise SourceError("access_denied")

    context.container.register_instance(SourceReader, SimpleNamespace(begin=begin))
    arguments = {
        "dataset_id": "local",
        "reader_source_connections": [{"provider": "google_drive", "connection_id": "alice-connection"}],
    }
    capture = native_read_capture(context)
    with pytest.raises(ToolError, match="Source read is unavailable"):
        await capture("bob", "north", "schema", arguments)
    schema.assert_not_awaited()
    result = await capture("alice", "north", "schema", arguments)
    assert result["tables"] == [{"name": "private"}]
    assert schema.await_count == 1
    receipts.record.assert_not_awaited()
    assert current_reader_choices("issuer|bob", "north") is None


async def test_curated_capture_serializes_native_typed_response_without_minting_receipt():
    class View(BaseModel):
        item_id: str
        version: int

    async def version(actor, tenant, item_id, selected):
        assert actor == "issuer|alice"
        assert current_reader_choices(actor, tenant) == ()
        return View(item_id=item_id, version=selected)

    context, receipts = application(SimpleNamespace())
    context.container.register_instance(CuratedKnowledgeReads, SimpleNamespace(version=version))
    result = await native_read_capture(context)(
        "alice", "north", "curated", {"source_id": "item", "version": 3, "reader_source_connections": []}
    )
    assert result["item_id"] == "item" and result["version"] == 3
    assert result["read_receipt"]["status"] == "not_recorded"
    receipts.record.assert_not_awaited()

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import GoneException, InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.attachments.ports import AttachmentBudget
from koinon.knowledge.attachments.service import AttachmentService
from koinon.knowledge.attachments.settings import AttachmentSettings


def prepared(content="Private facts"):
    @asynccontextmanager
    async def scope(*args, **kwargs):
        yield SimpleNamespace()

    row = SimpleNamespace(
        id="file",
        tenant_id="tenant",
        subject="issuer|owner",
        thread_id="thread",
        sha256=sha256(content.encode()).hexdigest(),
        revision=2,
        filename="private.txt",
        media_type="text/plain",
        kind="document",
        size_bytes=len(content.encode()),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        status="ready",
        text_char_count=len(content),
        chunk_count=1,
        normalized_media_type="text/plain",
        normalized_size_bytes=len(content.encode()),
        normalized_sha256=sha256(content.encode()).hexdigest(),
        warnings=[],
    )
    records = SimpleNamespace(selected=AsyncMock(return_value=[row]))
    storage = SimpleNamespace(read=AsyncMock(return_value=content.encode()))
    service = AttachmentService(
        SimpleNamespace(thread=AsyncMock()),
        SimpleNamespace(scope=scope),
        records,
        SimpleNamespace(page=AsyncMock(return_value=([], 0))),
        SimpleNamespace(),
        storage,
        AttachmentSettings(),
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
    )
    return service, row, storage


async def test_unknown_mixed_selection_is_rejected_before_any_private_bytes():
    service, _, storage = prepared()
    with pytest.raises(AccessDenied):
        await service.validate_selection("issuer|owner", "tenant", "thread", ["file", "foreign"])
    storage.read.assert_not_awaited()


async def test_expired_selection_and_duplicate_ids_never_read_bytes():
    service, row, storage = prepared()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with pytest.raises(GoneException):
        await service.validate_selection("issuer|owner", "tenant", "thread", ["file"])
    with pytest.raises(InvalidRequestException):
        await service.validate_selection("issuer|owner", "tenant", "thread", ["file", "file"])
    storage.read.assert_not_awaited()


async def test_complete_text_uses_exact_native_budget_and_does_not_silently_truncate():
    service, _, _ = prepared()
    refs = await service.validate_selection("issuer|owner", "tenant", "thread", ["file"])
    budget = AttachmentBudget(fits_text=AsyncMock(return_value=True))
    result = await service.content_for_model(
        "issuer|owner", "tenant", "thread", refs, question="Which facts?", budget=budget
    )
    assert result[0].complete and "Private facts" in result[0].text
    assert budget.fits_text.await_args.args[0] == result[0].text
    budget = AttachmentBudget(fits_text=AsyncMock(return_value=False))
    with pytest.raises(InvalidRequestException) as error:
        await service.content_for_model(
            "issuer|owner", "tenant", "thread", refs, question="Which facts?", budget=budget
        )
    assert error.value.code == "ATTACHMENT_CONTEXT_BUDGET_EXCEEDED"


async def test_unqualified_image_model_and_stale_digest_fail_before_binary_read():
    service, row, storage = prepared()
    row.kind, row.media_type, row.normalized_media_type = "image", "image/png", "image/png"
    refs = await service.validate_selection("issuer|owner", "tenant", "thread", ["file"])
    with pytest.raises(InvalidRequestException):
        await service.content_for_model(
            "issuer|owner",
            "tenant",
            "thread",
            refs,
            question="Describe",
            budget=AttachmentBudget(fits_text=AsyncMock(return_value=True)),
        )
    storage.read.assert_not_awaited()
    row.sha256 = "0" * 64
    with pytest.raises(AccessDenied):
        await service.authorize_evidence("issuer|owner", "tenant", "thread", refs)
    storage.read.assert_not_awaited()


async def test_removal_during_native_budget_check_revokes_prepared_content():
    service, row, _ = prepared()
    refs = await service.validate_selection("issuer|owner", "tenant", "thread", ["file"])

    async def fits(value):
        row.status = "deleted"
        return True

    with pytest.raises(GoneException):
        await service.content_for_model(
            "issuer|owner",
            "tenant",
            "thread",
            refs,
            question="Facts?",
            budget=AttachmentBudget(fits_text=fits),
        )

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact curated read capabilities do not escape their task or lifetime."""

import asyncio
from contextvars import copy_context

import pytest

from koinon.integrations.content_sources.errors import SourceError


@pytest.mark.asyncio
async def test_curated_capability_rejects_other_task_identity_version_and_expired_context(monkeypatch):
    from types import SimpleNamespace

    from koinon.integrations.content_sources.read_capabilities import (
        CuratedIdentity,
        curated_capability,
        curated_identity,
    )
    from koinon.security.authority import PRIMARY_POLICY_UNIT

    unit = SimpleNamespace(
        completed=False, read_only=True, definition=SimpleNamespace(name=PRIMARY_POLICY_UNIT)
    )
    current = unit
    monkeypatch.setattr(
        "koinon.integrations.content_sources.read_capabilities.current_unit_of_work", lambda _: current
    )
    identity = CuratedIdentity("item", "native-space", "native-item", "version-id", 1, "canonical-space")
    with curated_capability("reader", "tenant", (identity,)):
        assert curated_identity("reader", "tenant", "item", 1) == identity
        for actor, tenant, item, version in (
            ("other", "tenant", "item", 1),
            ("reader", "other", "item", 1),
            ("reader", "tenant", "other", 1),
            ("reader", "tenant", "item", 2),
        ):
            with pytest.raises(SourceError, match="authority_changed"):
                curated_identity(actor, tenant, item, version)

        async def copied_task():
            with pytest.raises(SourceError, match="authority_changed"):
                curated_identity("reader", "tenant", "item", 1)

        await asyncio.create_task(copied_task())
        current = SimpleNamespace(completed=False, read_only=True, definition=unit.definition)
        with pytest.raises(SourceError, match="authority_changed"):
            curated_identity("reader", "tenant", "item", 1)
        current = unit
        escaped = copy_context()
    with pytest.raises(SourceError, match="authority_changed"):
        escaped.run(curated_identity, "reader", "tenant", "item", 1)
    assert curated_identity("reader", "tenant", "item", 1) is None

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.data.relational.sqlalchemy import transactional
from test_membership_events import communications as communications

from koinon.communications.events import CommunicationEvents
from koinon.communications.repositories import NotificationRepository, OutboxRepository


@transactional
async def admit(context, **changes):
    await context.get_bean(CommunicationEvents).security_changed(
        "https://issuer.test|admin",
        "https://issuer.test|owner",
        "north",
        "token_created",
        "record-id",
        "Automation",
        scopes=["catalog:read"],
        **changes,
    )


async def test_required_security_notice_is_atomic_owner_only_and_contains_no_credentials(
    communications, monkeypatch
):
    await admit(communications)
    row = (await communications.get_bean(OutboxRepository).find_all(kind="security"))[0]
    assert row.owner_subject == "https://issuer.test|owner"
    assert row.event_json["subtype"] == "token_created"
    assert row.event_json["label"] == "Automation"
    assert row.event_json["scopes"] == ["catalog:read"]
    assert (
        len(await communications.get_bean(NotificationRepository).find_all(owner_subject=row.owner_subject))
        == 1
    )

    async def fail(*args, **kwargs):
        raise RuntimeError("owned rollback")

    monkeypatch.setattr(communications.get_bean(NotificationRepository), "save", fail)
    with pytest.raises(RuntimeError, match="owned rollback"):
        await admit(communications)
    assert len(await communications.get_bean(OutboxRepository).find_all(kind="security")) == 1


@transactional
async def invalid(context):
    await context.get_bean(CommunicationEvents).security_changed(
        "actor", "owner", "north", "unknown_kind", "id", "label"
    )


async def test_security_recorder_rejects_unknown_event_and_unbounded_header_data(communications):
    with pytest.raises(ValueError):
        await invalid(communications)

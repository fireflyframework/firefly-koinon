# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from fixture_readiness import OwnedReadiness
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.communications.administration import CommunicationsAdministration
from koinon.communications.configuration import CommunicationsConfiguration
from koinon.communications.events import CommunicationEvents
from koinon.communications.inbox import NotificationService
from koinon.communications.locale_service import CommunicationLocales
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.readiness import EmailReadiness
from koinon.communications.repositories import (
    CommunicationPolicyRepository,
    NotificationPreferenceRepository,
    NotificationRepository,
    OutboxRepository,
)
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.profiles.repositories import ProfileRepository


@pytest.fixture
async def communications(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'communications.db'}",
                        }
                    },
                }
            }
        )
    )
    scan_package("koinon.catalog", context.container)
    context.container.register_instance(CommunicationsSettings, CommunicationsSettings(enabled=True))
    context.container.register_instance(InstallationLinks, InstallationLinks())
    context.container.register_instance(EmailReadiness, OwnedReadiness())
    for kind in (
        CommunicationsAdministration,
        CommunicationLocales,
        CommunicationOutbox,
        NotificationRepository,
        OutboxRepository,
        CommunicationEvents,
        CommunicationsConfiguration,
        NotificationPreferenceRepository,
        CommunicationPolicyRepository,
        ProfileRepository,
        NotificationService,
    ):
        context.register_bean(kind)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
            await context.get_bean(MembershipRepository).save(
                Membership(
                    id=tenant + "-admin", subject="https://issuer.test|admin", tenant_id=tenant, role="admin"
                )
            )
        yield context
    finally:
        await context.stop()


async def test_membership_and_outbox_admit_in_same_transaction_and_noops_do_not_repeat(communications):
    catalog = communications.get_bean(CatalogService)
    outbox = communications.get_bean(OutboxRepository)
    inbox = communications.get_bean(NotificationRepository)
    member = await catalog.create_member(
        "https://issuer.test|admin", "north", subject="https://issuer.test|person", role="viewer"
    )
    assert len(await outbox.find_all(owner_subject=member.subject)) == 1
    assert (await inbox.find_all(owner_subject=member.subject))[0].kind == "access_granted"
    await catalog.update_member("https://issuer.test|admin", "north", member.id, role="viewer")
    assert len(await outbox.find_all(owner_subject=member.subject)) == 1
    await catalog.update_member("https://issuer.test|admin", "north", member.id, role="editor")
    await catalog.update_member("https://issuer.test|admin", "north", member.id, active=False)
    assert {row.kind for row in await inbox.find_all(owner_subject=member.subject)} == {
        "access_granted",
        "role_changed",
        "access_removed",
    }
    removal = (await outbox.find_all(kind="access_removed"))[0]
    assert removal.event_json["role"] == "editor" and removal.event_json["active"] is False
    assert removal.event_json["organization_name"] == "north"


async def test_notification_failure_rolls_back_membership_and_outbox(communications, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("test admission failure")

    monkeypatch.setattr(communications.get_bean(NotificationRepository), "save", fail)
    with pytest.raises(RuntimeError, match="test admission failure"):
        await communications.get_bean(CatalogService).create_member(
            "https://issuer.test|admin", "north", subject="https://issuer.test|rollback", role="viewer"
        )
    assert not await communications.get_bean(MembershipRepository).find_all(
        subject="https://issuer.test|rollback"
    )
    assert not await communications.get_bean(OutboxRepository).find_all(
        owner_subject="https://issuer.test|rollback"
    )


async def test_recorder_refuses_standalone_nontransactional_admission(communications):
    member = Membership(
        id="fake", tenant_id="north", subject="https://issuer.test|person", role="viewer", active=True
    )
    with pytest.raises(RuntimeError, match="transaction"):
        await communications.get_bean(CommunicationEvents).membership_changed(
            "https://issuer.test|admin", member, None
        )


async def test_disabled_email_still_admits_owner_inbox_and_terminal_suppressed_history(communications):
    communications.get_bean(EmailReadiness).state = "not_configured"
    member = await communications.get_bean(CatalogService).create_member(
        "https://issuer.test|admin", "north", subject="https://issuer.test|person", role="viewer"
    )
    row = (await communications.get_bean(OutboxRepository).find_all(owner_subject=member.subject))[0]
    assert row.status == "suppressed" and row.failure_code == "EMAIL_DISABLED"
    assert (
        len(await communications.get_bean(NotificationRepository).find_all(owner_subject=member.subject)) == 1
    )
    communications.get_bean(EmailReadiness).state = "ready"
    assert (await communications.get_bean(OutboxRepository).find_by_id(row.id)).status == "suppressed"

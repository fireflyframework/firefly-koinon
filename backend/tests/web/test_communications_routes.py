# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import ISSUER, bearer


def test_native_communications_fonts_are_packaged_and_pages_require_browser_session(client):
    font = client.get("/auth/communications/fonts/Inter.woff2")
    assert font.status_code == 200 and font.content.startswith(b"wOF2")
    assert len(font.content) > 10000
    denied = client.get("/auth/notifications", headers=bearer())
    assert denied.status_code == 403
    anonymous = client.get("/auth/notifications", follow_redirects=False)
    assert anonymous.status_code == 302 and anonymous.headers["location"] == "/oauth2/authorization/koinon"


def test_current_notification_http_contract_is_owner_scoped_and_read_only_without_membership_parameter(
    client,
):
    response = client.get("/api/v1/notifications", headers=bearer())
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    assert client.get("/api/v1/notifications/unread-count", headers=bearer()).json() == {"unread": 0}
    preferences = client.get("/api/v1/notifications/preferences", headers=bearer())
    assert preferences.status_code == 200, preferences.text
    assert preferences.json()["digest"] == "off"
    assert preferences.json()["effective_locale"] == "en-US"
    assert preferences.json()["locale_origin"] == "default"


def test_token_security_notices_share_native_mutation_and_never_store_returned_credentials(
    client, monkeypatch
):
    import json
    from datetime import UTC, datetime, timedelta

    import pytest

    from koinon.communications.repositories import NotificationRepository, OutboxRepository
    from koinon.communications.settings import CommunicationsSettings
    from koinon.tokens.repositories import PersonalTokenRepository
    from koinon.tokens.service import PersonalTokenService

    context = client.native_app.state.context
    context.get_bean(CommunicationsSettings).enabled = True
    service = context.get_bean(PersonalTokenService)
    values = dict(
        name="Owned automation",
        tenant_id="north",
        scopes=["catalog:read"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    async def create():
        return await service.create(f"{ISSUER}|admin", values)

    issued = client.portal.call(create)

    async def history():
        return await context.get_bean(OutboxRepository).find_all(kind="security")

    rows = client.portal.call(history)
    assert len(rows) == 1 and rows[0].event_json["subtype"] == "token_created"
    assert rows[0].status == "suppressed" and rows[0].failure_code == "EMAIL_DISABLED"
    assert issued["token"] not in json.dumps(rows[0].event_json)

    async def revoke():
        await service.revoke(f"{ISSUER}|admin", issued["id"])
        await service.revoke(f"{ISSUER}|admin", issued["id"])

    client.portal.call(revoke)
    assert len(client.portal.call(history)) == 2

    async def fail(*args, **kwargs):
        raise RuntimeError("owned notification rollback")

    monkeypatch.setattr(context.get_bean(NotificationRepository), "save", fail)
    with pytest.raises(RuntimeError, match="owned notification rollback"):
        client.portal.call(create)

    async def tokens():
        return await context.get_bean(PersonalTokenRepository).find_all(subject=f"{ISSUER}|admin")

    assert len(client.portal.call(tokens)) == 1
    assert len(client.portal.call(history)) == 2


def test_native_administrator_provision_uses_deferred_welcome_port_once_per_installation(client):
    from koinon.catalog.service import CatalogService
    from koinon.communications.repositories import OutboxRepository
    from koinon.communications.settings import CommunicationsSettings

    context = client.native_app.state.context
    context.get_bean(CommunicationsSettings).enabled = True

    async def provision():
        catalog = context.get_bean(CatalogService)
        member = await catalog.create_member(
            f"{ISSUER}|admin", "north", subject=f"{ISSUER}|new-admin", role="admin"
        )
        await catalog.update_member(f"{ISSUER}|admin", "north", member.id, role="viewer")
        await catalog.update_member(f"{ISSUER}|admin", "north", member.id, role="admin")
        return await context.get_bean(OutboxRepository).find_all(kind="welcome", owner_subject=member.subject)

    rows = client.portal.call(provision)
    assert len(rows) == 1 and rows[0].status == "suppressed"
    assert rows[0].failure_code == "EMAIL_DISABLED"

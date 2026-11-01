# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Public communications helpers round-trip the actual native HTTP contract."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import ApiError, KoinonClient
from koinon_sdk.activity import ActivityWindow
from koinon_sdk.communications import (
    ActivityEmailPreviewInput,
    CommunicationPolicyInput,
    DigestSchedule,
    EmailInvitationInput,
    NotificationPreferencesInput,
)
from koinon_sdk.organization_branding import BrandingValues

INVITATION = "11111111-1111-4111-8111-111111111111"
TENANT = "north/office"
AT = "2026-10-31T12:00:00Z"
RULE = dict(kind="digest", inbox=True, email=True)
PREFERENCES = NotificationPreferencesInput(
    expected_revision=7,
    rules=[RULE],
    digest="monthly",
    schedule=DigestSchedule(local_time="08:45", weekday=2, day_of_month=31),
    admin_summaries=False,
    notification_locale=None,
)
INVITE = EmailInvitationInput(
    recipient_ref="opaque-server-issued-ref", role="viewer", workspace_id="workspace", expires_in_hours=24
)
POLICY = CommunicationPolicyInput(
    expected_revision=3,
    sender_id=None,
    rules=[RULE],
    digest_enabled=True,
    allowed_digests=["off", "weekly", "monthly"],
    default_digest="monthly",
    default_schedule=PREFERENCES.schedule,
)
WINDOW = ActivityWindow(
    start_at=datetime(2026, 10, 1, tzinfo=UTC),
    end_at=datetime(2026, 10, 31, tzinfo=UTC),
    time_zone="Europe/Madrid",
)
PREVIEW = ActivityEmailPreviewInput(tenant_id=TENANT, preferences=PREFERENCES, window=WINDOW)


def responses():
    page = dict(total=0, page=1, page_size=20, pages=0, items=[])
    invitation = dict(
        id=INVITATION,
        tenant_id=TENANT,
        workspace_id="workspace",
        organization_name="Example organization",
        workspace_name="Example workspace",
        role="viewer",
        recipient_display_name="Example recipient",
        recipient_email="recipient@example.invalid",
        provider_label="Corporate directory",
        created_at=AT,
        expires_at="2026-11-01T12:00:00Z",
        status="pending",
        delivery=dict(id="delivery", status="unknown", queued_at=AT, failure_code="DELIVERY_OUTCOME_UNKNOWN"),
        allowed_actions=["revoke"],
        action_reasons={"resend": "delivery_outcome_unknown"},
    )
    review = dict(
        id=INVITATION,
        tenant_id=TENANT,
        organization_name="Example organization",
        workspace_id="workspace",
        workspace_name="Example workspace",
        role="viewer",
        expires_at="2026-11-01T12:00:00Z",
        status="pending",
        can_accept=True,
        can_decline=True,
        binding="directory_identity",
    )
    preview = dict(
        subject="Example invitation",
        sender_name="Example organization",
        recipient_display_name="Example recipient",
        recipient_email="recipient@example.invalid",
        heading="Review your access",
        paragraphs=["A directory-bound invitation."],
        action_label="Review invitation",
        footer="Powered by koinon",
        product_name="koinon",
        accent_color="#855414",
        branding=BrandingValues().model_dump(mode="json"),
        rendered_html="<p>Inert preview</p>",
        rendered_text="Inert preview",
        effective_locale="es-ES",
        locale_origin="installation",
    )
    preferences = dict(
        revision=8,
        rules=[dict(**RULE, required=False, email_available=False)],
        digest="monthly",
        allowed_digests=["off", "monthly"],
        locale="es-ES",
        time_zone="Europe/Madrid",
        schedule=PREFERENCES.schedule.model_dump(),
        notification_locale=None,
        next_run_at="2026-11-30T07:45:00Z",
        next_run_local="2026-11-30T08:45:00+01:00",
        effective_locale="es-ES",
        locale_origin="installation",
    )
    delivery = dict(
        id="delivery/one",
        kind="invitation",
        invitation_id=INVITATION,
        membership_id=None,
        recipient_display="Example recipient",
        scope_name="Example workspace",
        status="unknown",
        created_at=AT,
        last_attempt_at=None,
        next_attempt_at=None,
        attempt_count=1,
        failure_code="DELIVERY_OUTCOME_UNKNOWN",
        safe_explanation="Inspect the retained provider outcome.",
        can_retry=False,
    )
    notification = dict(
        id="notice/one",
        kind="security",
        title="API token revoked",
        body="Access changed.",
        created_at=AT,
        read_at=None,
        tenant_id=TENANT,
        organization_name="Example organization",
        target=dict(kind="none", id=None),
        details=dict(label="Example integration", scopes=["catalog:read"], expires_at=None),
    )
    return dict(
        page=page,
        invitation=invitation,
        review=review,
        preview=preview,
        preferences=preferences,
        delivery=delivery,
        notification=notification,
    )


CASES = [
    (
        "communication_providers",
        (TENANT,),
        dict(workspace_id="workspace", page=1, page_size=20),
        "GET",
        "/tenants/north%2Foffice/communications/recipient-providers",
        "page",
        None,
    ),
    (
        "communication_recipients",
        (TENANT,),
        dict(provider_id="provider", workspace_id="workspace", q="Example", after="opaque-cursor", limit=10),
        "GET",
        "/tenants/north%2Foffice/communications/recipients",
        "recipients",
        None,
    ),
    (
        "preview_email_invitation",
        (TENANT, INVITE),
        {},
        "POST",
        "/tenants/north%2Foffice/invitations/email/preview",
        "preview",
        INVITE,
    ),
    (
        "create_email_invitation",
        (TENANT, INVITE, "one-reviewed-action"),
        {},
        "POST",
        "/tenants/north%2Foffice/invitations/email",
        "invitation",
        INVITE,
    ),
    (
        "email_invitations",
        (TENANT,),
        dict(status="pending", page=2, page_size=10),
        "GET",
        "/tenants/north%2Foffice/invitations/email",
        "page",
        None,
    ),
    (
        "revoke_email_invitation",
        (TENANT, INVITATION),
        {},
        "DELETE",
        f"/tenants/north%2Foffice/invitations/email/{INVITATION}",
        "void",
        None,
    ),
    (
        "resend_email_invitation",
        (TENANT, INVITATION),
        {},
        "POST",
        f"/tenants/north%2Foffice/invitations/email/{INVITATION}/resend",
        "invitation",
        None,
    ),
    ("email_invitation", (INVITATION,), {}, "GET", f"/invitations/email/{INVITATION}", "review", None),
    (
        "accept_email_invitation",
        (INVITATION,),
        {},
        "POST",
        f"/invitations/email/{INVITATION}/accept",
        "member",
        None,
    ),
    (
        "decline_email_invitation",
        (INVITATION,),
        {},
        "POST",
        f"/invitations/email/{INVITATION}/decline",
        "review",
        None,
    ),
    (
        "communications_capabilities",
        (TENANT,),
        {},
        "GET",
        "/tenants/north%2Foffice/communications/capabilities",
        "capabilities",
        None,
    ),
    (
        "communications_policy",
        (TENANT,),
        {},
        "GET",
        "/tenants/north%2Foffice/communications/policy",
        "policy",
        None,
    ),
    (
        "update_communications_policy",
        (TENANT, POLICY),
        {},
        "PATCH",
        "/tenants/north%2Foffice/communications/policy",
        "policy",
        POLICY,
    ),
    (
        "communication_deliveries",
        (TENANT,),
        dict(
            kind="invitation",
            status="unknown",
            channel="email",
            workspace_id="workspace",
            created_from=AT,
            created_to="2026-11-01T12:00:00Z",
            page=2,
            page_size=10,
        ),
        "GET",
        "/tenants/north%2Foffice/communications/deliveries",
        "page",
        None,
    ),
    (
        "communication_delivery",
        (TENANT, "delivery/one"),
        {},
        "GET",
        "/tenants/north%2Foffice/communications/deliveries/delivery%2Fone",
        "delivery",
        None,
    ),
    (
        "retry_communication_delivery",
        (TENANT, "delivery/one"),
        {},
        "POST",
        "/tenants/north%2Foffice/communications/deliveries/delivery%2Fone/retry",
        "delivery",
        None,
    ),
    (
        "notifications",
        (),
        dict(tenant_id=TENANT, kind="security", read="unread", page=1, page_size=10),
        "GET",
        "/notifications",
        "page",
        None,
    ),
    ("notification_unread_count", (), {}, "GET", "/notifications/unread-count", "unread", None),
    (
        "read_notification",
        ("notice/one",),
        {},
        "POST",
        "/notifications/notice%2Fone/read",
        "notification",
        None,
    ),
    ("notification_preferences", (), {}, "GET", "/notifications/preferences", "preferences", None),
    (
        "update_notification_preferences",
        (PREFERENCES,),
        {},
        "PATCH",
        "/notifications/preferences",
        "preferences",
        PREFERENCES,
    ),
    (
        "preview_notification_schedule",
        (PREFERENCES,),
        {},
        "POST",
        "/notifications/preferences/preview",
        "schedule",
        PREFERENCES,
    ),
    (
        "preview_activity_email",
        (PREVIEW,),
        {},
        "POST",
        "/notifications/preferences/email-preview",
        "preview",
        PREVIEW,
    ),
]


@pytest.mark.parametrize(
    "name,args,filters,method,path,result_kind,body", CASES, ids=[case[0] for case in CASES]
)
async def test_all_23_operations_use_native_routes_typed_payloads_and_caller_auth(
    name, args, filters, method, path, result_kind, body
):
    payloads = responses()
    payloads.update(
        recipients=dict(
            items=[
                dict(
                    recipient_ref="opaque-server-issued-ref",
                    display_name="Example recipient",
                    email="recipient@example.invalid",
                    provider_label="Corporate directory",
                    delivery_address_status="verified_directory",
                    eligibility="eligible",
                )
            ],
            next_cursor=None,
        ),
        member=dict(
            id="member",
            subject="https://issuer.invalid|signed-sub",
            tenant_id=TENANT,
            workspace_id="workspace",
            role="viewer",
            active=True,
            created_at=AT,
        ),
        capabilities=dict(
            state="not_configured",
            provider_label="",
            sender_name="",
            sender_address="",
            sender_options=[],
            public_address_configured=True,
            public_url="https://brain.invalid",
            acceptance_base="/auth/invitations/email",
            issues=[dict(code="EMAIL_NOT_CONFIGURED", explanation="Configure a real provider.")],
        ),
        policy=dict(revision=4, sender_id=None, rules=[], digest_enabled=False, can_update=True),
        unread=dict(unread=3),
        schedule=dict(
            digest="monthly",
            schedule=PREFERENCES.schedule.model_dump(),
            time_zone="Europe/Madrid",
            next_run_at="2026-11-30T07:45:00Z",
            next_run_local="2026-11-30T08:45:00+01:00",
            window_start=AT,
            window_end="2026-11-30T07:45:00Z",
        ),
    )
    seen = []

    def handle(request):
        seen.append(request)
        assert request.method == method
        assert request.url.raw_path.split(b"?")[0] == ("/api/v1" + path).encode()
        assert dict(request.url.params) == {key: str(value) for key, value in filters.items()}
        assert "event_kind" not in request.url.params
        assert request.headers["Authorization"] == "Bearer inert-fresh-caller"
        if body is not None:
            assert json.loads(request.content) == body.model_dump(mode="json", exclude_unset=True)
        else:
            assert not request.content
        if name == "create_email_invitation":
            assert request.headers["Idempotency-Key"] == "one-reviewed-action"
        else:
            assert "Idempotency-Key" not in request.headers
        return (
            httpx.Response(204) if result_kind == "void" else httpx.Response(200, json=payloads[result_kind])
        )

    async with KoinonClient(
        "https://brain.invalid/api/v1",
        token_provider=lambda: "inert-fresh-caller",
        transport=httpx.MockTransport(handle),
    ) as client:
        result = await getattr(client, name)(*args, **filters)
    assert len(seen) == 1
    if result_kind == "void":
        assert result is None
    else:
        assert not isinstance(result, dict)
    if result_kind == "invitation":
        assert result.expires_at.utcoffset().total_seconds() == 0
        assert result.delivery.status == "unknown" and "token" not in result.model_dump()
        assert result.action_reasons["resend"] == "delivery_outcome_unknown"
    if result_kind == "review":
        assert result.binding == "directory_identity" and result.id == INVITATION
    if result_kind == "capabilities":
        assert result.public_url == "https://brain.invalid"
        assert result.acceptance_base == "/auth/invitations/email"
    if result_kind == "notification":
        assert result.read_at is None and result.details.expires_at is None
    if result_kind == "preferences":
        assert result.notification_locale is None and result.locale_origin == "installation"
        assert result.schedule.day_of_month == 31 and result.next_run_at.hour == 7


async def test_auth_refresh_and_server_errors_are_not_retried_or_hidden():
    seen = []
    tokens = iter(("first-caller-token", "replacement-token"))

    async def token():
        return next(tokens)

    def handle(request):
        seen.append(request)
        if len(seen) == 1:
            return httpx.Response(200, json={"unread": 2})
        return httpx.Response(
            409,
            json={
                "code": "INVITATION_RECIPIENT_MISMATCH",
                "detail": "Sign in as the intended directory recipient.",
            },
            headers={"X-Request-Id": "inert-request"},
        )

    async with KoinonClient(
        "https://brain.invalid/api/v1", token_provider=token, transport=httpx.MockTransport(handle)
    ) as client:
        assert (await client.notification_unread_count()).unread == 2
        with pytest.raises(ApiError) as error:
            await client.email_invitation(INVITATION)
        assert error.value.status == 409 and error.value.code == "INVITATION_RECIPIENT_MISMATCH"
        assert error.value.request_id == "inert-request"
    assert [request.headers["Authorization"] for request in seen] == [
        "Bearer first-caller-token",
        "Bearer replacement-token",
    ]


async def test_cancelled_inbox_read_cancels_transport_without_retry():
    entered = asyncio.Event()
    cancelled = asyncio.Event()
    calls = 0

    async def handle(request):
        nonlocal calls
        calls += 1
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        raise AssertionError("Unreachable response")

    async with KoinonClient(
        "https://brain.invalid/api/v1", token_provider=lambda: "inert", transport=httpx.MockTransport(handle)
    ) as client:
        task = asyncio.create_task(client.notifications(read="unread"))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled.is_set() and calls == 1


@pytest.mark.parametrize(
    "name,args",
    [
        ("email_invitation", ()),
        ("accept_email_invitation", ()),
        ("decline_email_invitation", ()),
        ("resend_email_invitation", (TENANT,)),
        ("revoke_email_invitation", (TENANT,)),
    ],
)
async def test_email_routes_reject_bearer_strings_before_http(name, args):
    def handle(request):
        pytest.fail("A credential-like path must never reach HTTP")

    async with KoinonClient(
        "https://brain.invalid/api/v1", token_provider=lambda: "inert", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ValueError):
            await getattr(client, name)(*args, "credential-like-value")


@pytest.mark.parametrize("value", [dict(expires_in_hours=169), dict(expires_in_hours=0), dict(role="owner")])
def test_email_invitation_input_retains_server_contract_bounds(value):
    with pytest.raises(ValidationError):
        EmailInvitationInput.model_validate({**INVITE.model_dump(), **value})

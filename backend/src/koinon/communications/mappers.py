# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta

from koinon.communications.dtos import (
    EmailInvitation,
    InvitationDelivery,
    InvitationReview,
    NotificationDetails,
    NotificationTarget,
    OwnNotification,
)
from koinon.communications.locales import LocaleOrigin, translate


def invitation_status(row, now):
    if row.accepted_at:
        return "accepted"
    if row.declined_at:
        return "declined"
    if row.revoked_at:
        return "revoked"
    return "expired" if row.expires_at <= now else "pending"


def invitation_dto(row, recipient, delivery, now, settings):
    status = invitation_status(row, now)
    next_resend = row.last_queued_at + timedelta(seconds=settings.resend_cooldown_seconds)
    actions = []
    if status == "pending":
        actions.append("revoke")
        if (
            next_resend <= now
            and row.send_count < settings.max_invitation_sends
            and delivery.status not in {"sending", "preparing", "unknown"}
        ):
            actions.append("resend")
    return EmailInvitation(
        id=row.id,
        tenant_id=row.tenant_id,
        workspace_id=row.workspace_id,
        organization_name=recipient["organization_name"],
        workspace_name=recipient.get("workspace_name"),
        role=row.role,
        recipient_display_name=recipient["display_name"],
        recipient_email=recipient["email"],
        provider_label=recipient["provider_label"],
        created_at=row.created_at,
        expires_at=row.expires_at,
        status=status,
        accepted_at=row.accepted_at,
        declined_at=row.declined_at,
        revoked_at=row.revoked_at,
        delivery=InvitationDelivery(
            id=delivery.id,
            status="queued" if delivery.status == "preparing" else delivery.status,
            queued_at=delivery.created_at,
            last_attempt_at=delivery.last_attempt_at,
            next_attempt_at=delivery.next_attempt_at if delivery.status in {"queued", "deferred"} else None,
            next_resend_at=next_resend if status == "pending" else None,
            failure_code=delivery.failure_code,
        ),
        allowed_actions=actions,
    )


def invitation_review(row, recipient, now, *, can_accept):
    status = invitation_status(row, now)
    return InvitationReview(
        id=row.id,
        tenant_id=row.tenant_id,
        organization_name=recipient["organization_name"],
        workspace_id=row.workspace_id,
        workspace_name=recipient.get("workspace_name"),
        role=row.role,
        expires_at=row.expires_at,
        status=status,
        can_accept=status == "pending" and can_accept,
        can_decline=status == "pending",
    )


def notification_dto(
    row, *, can_navigate=False, locale="en-US", locale_origin: LocaleOrigin = "default", details=None
):
    target = NotificationTarget(kind="none")
    if can_navigate and row.kind != "access_removed":
        if row.invitation_id:
            target = NotificationTarget(kind="invitation", id=row.invitation_id)
        elif row.workspace_id:
            target = NotificationTarget(kind="workspace", id=row.workspace_id)
    kind = row.kind
    title = translate(locale, kind + "_title")
    if kind == "security":
        event = (details or {}).get("subtype")
        body = (
            translate(locale, "security_" + event)
            if event
            in {
                "token_created",
                "token_revoked",
                "application_granted",
                "application_revoked",
                "client_registered",
                "client_revoked",
                "client_secret_rotated",
                "client_changed",
            }
            else title
        )
    else:
        body = translate(locale, kind + "_body")
    metadata = details or {}
    return OwnNotification(
        workspace_name=metadata.get("workspace_name"),
        actor_name=metadata.get("actor_name"),
        details=NotificationDetails(
            label=metadata.get("label"),
            scopes=metadata.get("scopes", []),
            expires_at=metadata.get("expires_at"),
        )
        if kind == "security"
        else None,
        id=row.id,
        kind=row.kind,
        title=title,
        body=body,
        created_at=row.created_at,
        read_at=row.read_at,
        tenant_id=row.tenant_id,
        organization_name=row.organization_name,
        target=target,
        effective_locale=locale,
        locale_origin=locale_origin,
    )

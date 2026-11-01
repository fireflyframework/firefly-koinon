# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Admit references inside the mutation's primary transaction; never dispatch here."""

from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.transaction import current_unit_of_work

from koinon.catalog.repositories import CatalogRepository, TenantRepository
from koinon.communications.entities import NotificationRecord, OutboxRecord
from koinon.communications.ports import WelcomeAdmissionPort
from koinon.communications.readiness import EmailReadiness
from koinon.communications.repositories import (
    CommunicationPolicyRepository,
    NotificationRepository,
    OutboxRepository,
)
from koinon.communications.settings import CommunicationsSettings
from koinon.profiles.repositories import ProfileRepository
from koinon.profiles.service import profile_id


@service(name="communications.events")
class CommunicationEvents:
    def __init__(
        self,
        outbox: OutboxRepository,
        notifications: NotificationRepository,
        tenants: TenantRepository,
        settings: CommunicationsSettings,
        readiness: EmailReadiness | None = None,
        entries: CatalogRepository | None = None,
        profiles: ProfileRepository | None = None,
        policies: CommunicationPolicyRepository | None = None,
        welcomes: Provider[WelcomeAdmissionPort | None] | None = None,
    ):
        self.outbox, self.notifications, self.tenants, self.settings = (
            outbox,
            notifications,
            tenants,
            settings,
        )
        self.readiness, self.welcomes = readiness, welcomes
        self.entries, self.profiles, self.policies = entries, profiles, policies

    def require_mutation(self):
        unit = current_unit_of_work("primary")
        if unit is None or unit.completed or unit.read_only or not unit.read_from_primary:
            raise RuntimeError("Communications admission requires the current primary mutation transaction")

    async def membership_changed(self, actor, member, before):
        if not self.settings.enabled:
            return
        self.require_mutation()
        old_active, old_role = before or (False, member.role)
        if member.active and not old_active:
            kind = "access_granted"
        elif old_active and not member.active:
            kind = "access_removed"
        elif old_active and member.active and old_role != member.role:
            kind = "role_changed"
        else:
            return
        if (
            member.active
            and member.role == "admin"
            and member.workspace_id is None
            and (not old_active or old_role != "admin")
        ):
            welcome = self.welcomes.get() if self.welcomes is not None else None
            if welcome is not None:
                await welcome.admit(member.subject, member.tenant_id)
        now = await self.outbox.clock()
        email_ready = await self.email_ready(member.tenant_id)
        provenance = await self.provenance(actor, member.tenant_id, member.workspace_id)
        identifier = str(uuid4())
        await self.outbox.save(
            OutboxRecord(
                id=identifier,
                dedupe_key=identifier,
                tenant_id=member.tenant_id,
                workspace_id=member.workspace_id,
                owner_subject=member.subject,
                kind=kind,
                membership_id=member.id,
                event_json={"role": member.role, "active": member.active, **provenance},
                status="queued" if email_ready else "suppressed",
                failure_code=None if email_ready else "EMAIL_DISABLED",
                completed_at=None if email_ready else now,
                created_at=now,
                next_attempt_at=now,
            )
        )
        tenant = await self.tenants.find_by_id(member.tenant_id)
        await self.notifications.save(
            NotificationRecord(
                id=str(uuid4()),
                event_id=identifier,
                owner_subject=member.subject,
                tenant_id=member.tenant_id,
                kind=kind,
                organization_name=tenant.name,
                workspace_id=member.workspace_id,
                membership_id=member.id,
                created_at=now,
            )
        )

    async def security_changed(
        self,
        actor,
        owner,
        tenant_id,
        subtype,
        resource_id,
        label,
        *,
        scopes=None,
        expires_at=None,
        workspace_id=None,
    ):
        if not self.settings.enabled:
            return
        self.require_mutation()
        allowed = {
            "token_created",
            "token_revoked",
            "application_granted",
            "application_revoked",
            "client_registered",
            "client_revoked",
            "client_secret_rotated",
            "client_changed",
        }
        if (
            subtype not in allowed
            or not isinstance(label, str)
            or not 1 <= len(label) <= 200
            or any(ord(c) < 32 or ord(c) == 127 for c in label)
            or len(scopes or []) > 100
            or any(
                not isinstance(scope, str)
                or len(scope) > 100
                or any(ord(c) < 33 or ord(c) > 126 for c in scope)
                for scope in scopes or []
            )
        ):
            raise ValueError(
                "Security notifications require fixed event kinds and bounded credential-free metadata"
            )
        now = await self.outbox.clock()
        identifier = str(uuid4())
        ready = await self.email_ready(tenant_id)
        tenant = await self.tenants.find_by_id(tenant_id)
        await self.outbox.save(
            OutboxRecord(
                id=identifier,
                dedupe_key=identifier,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                owner_subject=owner,
                kind="security",
                event_json=dict(
                    subtype=subtype,
                    label=label,
                    scopes=sorted(set(scopes or [])),
                    expires_at=expires_at.isoformat() if expires_at else None,
                    **await self.provenance(actor, tenant_id, workspace_id),
                ),
                status="queued" if ready else "suppressed",
                failure_code=None if ready else "EMAIL_DISABLED",
                completed_at=None if ready else now,
                created_at=now,
                next_attempt_at=now,
            )
        )
        await self.notifications.save(
            NotificationRecord(
                id=str(uuid4()),
                event_id=identifier,
                owner_subject=owner,
                tenant_id=tenant_id,
                kind="security",
                organization_name=tenant.name,
                workspace_id=workspace_id,
                created_at=now,
            )
        )

    async def email_ready(self, tenant_id):
        policy = await self.policies.find_by_id(tenant_id) if self.policies else None
        return (
            self.readiness is not None
            and self.readiness.observe(sender_id=policy.sender_id if policy else None).state == "ready"
        )

    async def provenance(self, actor, tenant_id, workspace_id):
        tenant = await self.tenants.find_by_id(tenant_id)
        workspace = await self.entries.find_by_id(workspace_id) if workspace_id and self.entries else None
        profile = await self.profiles.find_by_id(profile_id(actor)) if self.profiles else None
        return dict(
            organization_name=tenant.name,
            workspace_name=workspace.name if workspace and workspace.tenant_id == tenant_id else None,
            actor_name=profile.display_name if profile and profile.display_name.strip() else None,
        )

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Credential-free recipient invitations and subject-owned notification endpoints."""

from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    patch_mapping,
    post_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.api.controllers.memberships import invitation_identity
from koinon.catalog.mappers import member_dto
from koinon.communications.administration import CommunicationsAdministration
from koinon.communications.content import CommunicationContent
from koinon.communications.dtos import (
    ActivityEmailPreviewInput,
    CommunicationCapabilities,
    CommunicationPolicy,
    CommunicationPolicyInput,
    DeliveryPage,
    DeliveryRecord,
    DigestSchedulePreview,
    DirectoryRecipientPage,
    EmailInvitation,
    EmailInvitationInput,
    EmailInvitationPage,
    EmailPreview,
    InvitationReview,
    NotificationPreferences,
    NotificationPreferencesInput,
    NotificationUnreadCount,
    OwnNotification,
    OwnNotificationPage,
    RecipientProviderPage,
)
from koinon.communications.inbox import NotificationService
from koinon.communications.invitations import EmailInvitationService
from koinon.communications.preview import ActivityEmailPreviewService
from koinon.communications.recipients import RecipientService
from koinon.profiles.security import require_personal_permission
from koinon.security.identity import identity_from_request


@rest_controller(name="communications.controller")
@request_mapping("/api/v1")
class CommunicationsController:
    def __init__(
        self,
        recipients: RecipientService,
        invitations: EmailInvitationService,
        content: CommunicationContent,
        administration: CommunicationsAdministration,
    ):
        self.recipients, self.invitations, self.content, self.administration = (
            recipients,
            invitations,
            content,
            administration,
        )

    @get_mapping("/tenants/{tenant_id}/communications/recipient-providers")
    async def providers(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 20,
    ) -> RecipientProviderPage:
        return await self.recipients.providers_page(
            identity_from_request(request).subject,
            tenant_id,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/tenants/{tenant_id}/communications/recipients")
    async def recipients_search(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        provider_id: QueryParam[str | None] = None,
        workspace_id: QueryParam[str | None] = None,
        after: QueryParam[str | None] = None,
        limit: QueryParam[int] = 20,
    ) -> DirectoryRecipientPage:
        return await self.recipients.search(
            identity_from_request(request).subject,
            tenant_id,
            q=q,
            provider_id=provider_id,
            workspace_id=workspace_id,
            after=after,
            limit=limit,
        )

    @post_mapping("/tenants/{tenant_id}/invitations/email/preview")
    async def preview(
        self, tenant_id: PathVar[str], body: Valid[Body[EmailInvitationInput]], request: Request
    ) -> EmailPreview:
        return await self.content.preview_invitation(identity_from_request(request).subject, tenant_id, body)

    @post_mapping("/tenants/{tenant_id}/invitations/email", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[EmailInvitationInput]], request: Request
    ) -> EmailInvitation:
        return await self.invitations.create(
            identity_from_request(request).subject, tenant_id, body, request.headers.get("idempotency-key")
        )

    @get_mapping("/tenants/{tenant_id}/invitations/email")
    async def page(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        status: QueryParam[str] = "pending",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> EmailInvitationPage:
        return await self.invitations.page(
            identity_from_request(request).subject,
            tenant_id,
            workspace_id=workspace_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    @delete_mapping("/tenants/{tenant_id}/invitations/email/{invitation_id}", status_code=204)
    async def revoke(self, tenant_id: PathVar[str], invitation_id: PathVar[str], request: Request) -> None:
        await self.invitations.revoke(identity_from_request(request).subject, tenant_id, invitation_id)

    @post_mapping("/tenants/{tenant_id}/invitations/email/{invitation_id}/resend")
    async def resend(
        self, tenant_id: PathVar[str], invitation_id: PathVar[str], request: Request
    ) -> EmailInvitation:
        return await self.invitations.resend(identity_from_request(request).subject, tenant_id, invitation_id)

    @get_mapping("/invitations/email/{invitation_id}")
    async def inspect(self, invitation_id: PathVar[str], request: Request) -> InvitationReview:
        return await self.invitations.review(
            invitation_identity(request), invitation_id, request.state.security_context.attributes
        )

    @post_mapping("/invitations/email/{invitation_id}/accept")
    async def accept(self, invitation_id: PathVar[str], request: Request) -> dict:
        return member_dto(
            await self.invitations.accept(
                invitation_identity(request), invitation_id, request.state.security_context.attributes
            )
        )

    @post_mapping("/invitations/email/{invitation_id}/decline")
    async def decline(self, invitation_id: PathVar[str], request: Request) -> InvitationReview:
        return await self.invitations.decline(
            invitation_identity(request), invitation_id, request.state.security_context.attributes
        )

    @get_mapping("/tenants/{tenant_id}/communications/capabilities")
    async def capabilities(self, tenant_id: PathVar[str], request: Request) -> CommunicationCapabilities:
        return await self.administration.capabilities(identity_from_request(request).subject, tenant_id)

    @get_mapping("/tenants/{tenant_id}/communications/policy")
    async def policy(self, tenant_id: PathVar[str], request: Request) -> CommunicationPolicy:
        return await self.administration.policy(identity_from_request(request).subject, tenant_id)

    @patch_mapping("/tenants/{tenant_id}/communications/policy")
    async def policy_update(
        self, tenant_id: PathVar[str], body: Valid[Body[CommunicationPolicyInput]], request: Request
    ) -> CommunicationPolicy:
        return await self.administration.update_policy(
            identity_from_request(request).subject, tenant_id, body
        )

    @get_mapping("/tenants/{tenant_id}/communications/deliveries")
    async def deliveries(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        status: QueryParam[str | None] = None,
        kind: QueryParam[str | None] = None,
        channel: QueryParam[str] = "email",
        created_from: QueryParam[str | None] = None,
        created_to: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> DeliveryPage:
        return await self.administration.deliveries(
            identity_from_request(request).subject,
            tenant_id,
            workspace_id=workspace_id,
            status=status,
            kind=kind,
            channel=channel,
            created_from=created_from,
            created_to=created_to,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/tenants/{tenant_id}/communications/deliveries/{delivery_id}")
    async def delivery(
        self, tenant_id: PathVar[str], delivery_id: PathVar[str], request: Request
    ) -> DeliveryRecord:
        return await self.administration.delivery(
            identity_from_request(request).subject, tenant_id, delivery_id
        )

    @post_mapping("/tenants/{tenant_id}/communications/deliveries/{delivery_id}/retry")
    async def retry(
        self, tenant_id: PathVar[str], delivery_id: PathVar[str], request: Request
    ) -> DeliveryRecord:
        return await self.administration.retry(identity_from_request(request).subject, tenant_id, delivery_id)


@rest_controller(name="communications.notifications_controller")
@request_mapping("/api/v1/notifications")
class NotificationController:
    def __init__(
        self, notifications: NotificationService, previews: ActivityEmailPreviewService | None = None
    ):
        self.notifications, self.previews = notifications, previews

    @get_mapping("")
    async def page(
        self,
        request: Request,
        tenant_id: QueryParam[str | None] = None,
        kind: QueryParam[str | None] = None,
        read: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> OwnNotificationPage:
        return await self.notifications.page(
            require_personal_permission(request, "notifications:read").subject,
            tenant_id=tenant_id,
            kind=kind,
            read=read,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/unread-count")
    async def unread_count(self, request: Request) -> NotificationUnreadCount:
        return await self.notifications.unread_count(
            require_personal_permission(request, "notifications:read").subject
        )

    @post_mapping("/{notification_id}/read")
    async def read(self, notification_id: PathVar[str], request: Request) -> OwnNotification:
        return await self.notifications.mark_read(
            require_personal_permission(request, "notifications:write").subject, notification_id
        )

    @get_mapping("/preferences")
    async def preferences(self, request: Request) -> NotificationPreferences:
        return await self.notifications.preferences(
            require_personal_permission(request, "notifications:read").subject
        )

    @patch_mapping("/preferences")
    async def preferences_update(
        self, body: Valid[Body[NotificationPreferencesInput]], request: Request
    ) -> NotificationPreferences:
        return await self.notifications.update_preferences(
            require_personal_permission(request, "notifications:write").subject, body
        )

    @post_mapping("/preferences/preview")
    async def preferences_preview(
        self, body: Valid[Body[NotificationPreferencesInput]], request: Request
    ) -> DigestSchedulePreview:
        return await self.notifications.preview_schedule(
            require_personal_permission(request, "notifications:read").subject, body
        )

    @post_mapping("/preferences/email-preview")
    async def email_preview(
        self, body: Valid[Body[ActivityEmailPreviewInput]], request: Request
    ) -> EmailPreview:
        owner = require_personal_permission(request, "notifications:read").subject
        require_personal_permission(request, "activity:read")
        if self.previews is None:
            from pyfly.kernel import ServiceUnavailableException

            raise ServiceUnavailableException(
                "Activity email previews are not configured", code="ACTIVITY_SUMMARIES_UNAVAILABLE"
            )
        return await self.previews.preview(owner, body)

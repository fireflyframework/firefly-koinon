# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed communications operations share the client's existing authenticated transport."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar, Unpack
from urllib.parse import quote
from uuid import UUID

from pydantic import BaseModel

from koinon_sdk.communication_filters import (
    CommunicationDeliveryFilter,
    EmailInvitationFilter,
    NotificationFilter,
    RecipientFilter,
    RecipientProviderFilter,
)
from koinon_sdk.communications import (
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
from koinon_sdk.models import Membership

Result = TypeVar("Result", bound=BaseModel)


class CommunicationsClientMixin(ABC):
    @staticmethod
    @abstractmethod
    def _tenant(tenant_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def _communication(self, result: type[Result], method: str, path: str, **kwargs: Any) -> Result:
        return result.model_validate(await self._request(method, path, **kwargs))

    def _communication_path(self, tenant_id: str, suffix: str) -> str:
        return self._tenant(tenant_id) + "/communications" + suffix

    def _email_invitation_path(self, tenant_id: str, invitation_id: str | None = None) -> str:
        return (
            self._tenant(tenant_id)
            + "/invitations/email"
            + ("/" + str(UUID(invitation_id)) if invitation_id is not None else "")
        )

    @staticmethod
    def _recipient_invitation_path(invitation_id: str) -> str:
        return "/invitations/email/" + str(UUID(invitation_id))

    async def communication_providers(
        self, tenant_id: str, **filters: Unpack[RecipientProviderFilter]
    ) -> RecipientProviderPage:
        return await self._communication(
            RecipientProviderPage,
            "GET",
            self._communication_path(tenant_id, "/recipient-providers"),
            params=filters,
        )

    async def communication_recipients(
        self, tenant_id: str, **filters: Unpack[RecipientFilter]
    ) -> DirectoryRecipientPage:
        return await self._communication(
            DirectoryRecipientPage, "GET", self._communication_path(tenant_id, "/recipients"), params=filters
        )

    async def preview_email_invitation(self, tenant_id: str, value: EmailInvitationInput) -> EmailPreview:
        return await self._communication(
            EmailPreview,
            "POST",
            self._email_invitation_path(tenant_id) + "/preview",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def create_email_invitation(
        self, tenant_id: str, value: EmailInvitationInput, idempotency_key: str
    ) -> EmailInvitation:
        return await self._communication(
            EmailInvitation,
            "POST",
            self._email_invitation_path(tenant_id),
            json=value.model_dump(mode="json", exclude_unset=True),
            headers={"Idempotency-Key": idempotency_key},
        )

    async def email_invitations(
        self, tenant_id: str, **filters: Unpack[EmailInvitationFilter]
    ) -> EmailInvitationPage:
        return await self._communication(
            EmailInvitationPage, "GET", self._email_invitation_path(tenant_id), params=filters
        )

    async def revoke_email_invitation(self, tenant_id: str, invitation_id: str) -> None:
        await self._request("DELETE", self._email_invitation_path(tenant_id, invitation_id))

    async def resend_email_invitation(self, tenant_id: str, invitation_id: str) -> EmailInvitation:
        return await self._communication(
            EmailInvitation, "POST", self._email_invitation_path(tenant_id, invitation_id) + "/resend"
        )

    async def email_invitation(self, invitation_id: str) -> InvitationReview:
        return await self._communication(
            InvitationReview, "GET", self._recipient_invitation_path(invitation_id)
        )

    async def accept_email_invitation(self, invitation_id: str) -> Membership:
        return await self._communication(
            Membership, "POST", self._recipient_invitation_path(invitation_id) + "/accept"
        )

    async def decline_email_invitation(self, invitation_id: str) -> InvitationReview:
        return await self._communication(
            InvitationReview, "POST", self._recipient_invitation_path(invitation_id) + "/decline"
        )

    async def communications_capabilities(self, tenant_id: str) -> CommunicationCapabilities:
        return await self._communication(
            CommunicationCapabilities, "GET", self._communication_path(tenant_id, "/capabilities")
        )

    async def communications_policy(self, tenant_id: str) -> CommunicationPolicy:
        return await self._communication(
            CommunicationPolicy, "GET", self._communication_path(tenant_id, "/policy")
        )

    async def update_communications_policy(
        self, tenant_id: str, value: CommunicationPolicyInput
    ) -> CommunicationPolicy:
        return await self._communication(
            CommunicationPolicy,
            "PATCH",
            self._communication_path(tenant_id, "/policy"),
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def communication_deliveries(
        self, tenant_id: str, **filters: Unpack[CommunicationDeliveryFilter]
    ) -> DeliveryPage:
        return await self._communication(
            DeliveryPage, "GET", self._communication_path(tenant_id, "/deliveries"), params=filters
        )

    async def communication_delivery(self, tenant_id: str, delivery_id: str) -> DeliveryRecord:
        return await self._communication(
            DeliveryRecord,
            "GET",
            self._communication_path(tenant_id, "/deliveries/" + quote(delivery_id, safe="")),
        )

    async def retry_communication_delivery(self, tenant_id: str, delivery_id: str) -> DeliveryRecord:
        return await self._communication(
            DeliveryRecord,
            "POST",
            self._communication_path(tenant_id, "/deliveries/" + quote(delivery_id, safe="") + "/retry"),
        )

    async def notifications(self, **filters: Unpack[NotificationFilter]) -> OwnNotificationPage:
        return await self._communication(OwnNotificationPage, "GET", "/notifications", params=filters)

    async def notification_unread_count(self) -> NotificationUnreadCount:
        return await self._communication(NotificationUnreadCount, "GET", "/notifications/unread-count")

    async def read_notification(self, notification_id: str) -> OwnNotification:
        return await self._communication(
            OwnNotification, "POST", "/notifications/" + quote(notification_id, safe="") + "/read"
        )

    async def notification_preferences(self) -> NotificationPreferences:
        return await self._communication(NotificationPreferences, "GET", "/notifications/preferences")

    async def update_notification_preferences(
        self, value: NotificationPreferencesInput
    ) -> NotificationPreferences:
        return await self._communication(
            NotificationPreferences,
            "PATCH",
            "/notifications/preferences",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def preview_notification_schedule(
        self, value: NotificationPreferencesInput
    ) -> DigestSchedulePreview:
        return await self._communication(
            DigestSchedulePreview,
            "POST",
            "/notifications/preferences/preview",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

    async def preview_activity_email(self, value: ActivityEmailPreviewInput) -> EmailPreview:
        return await self._communication(
            EmailPreview,
            "POST",
            "/notifications/preferences/email-preview",
            json=value.model_dump(mode="json", exclude_unset=True),
        )

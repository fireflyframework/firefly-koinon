# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only filters declared by the communications API are accepted by typed helpers."""

from typing import Literal, TypedDict

from koinon_sdk.communications import DeliveryStatus, EventKind


class CommunicationPageFilter(TypedDict, total=False):
    page: int
    page_size: int


class RecipientProviderFilter(CommunicationPageFilter, total=False):
    workspace_id: str


class RecipientFilter(TypedDict, total=False):
    q: str
    provider_id: str
    workspace_id: str
    after: str
    limit: int


class EmailInvitationFilter(CommunicationPageFilter, total=False):
    workspace_id: str
    status: Literal["pending", "accepted", "declined", "revoked", "expired"]


class CommunicationDeliveryFilter(CommunicationPageFilter, total=False):
    workspace_id: str
    status: DeliveryStatus
    kind: EventKind
    channel: Literal["email"]
    created_from: str
    created_to: str


class NotificationFilter(CommunicationPageFilter, total=False):
    tenant_id: str
    kind: EventKind
    read: Literal["all", "unread", "read"]

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/organization_chat/dtos.py
SHA256: 7ccde6a1bb0815b92c837de290473619592bc38fc900f78a07c5217c0efddb1b

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel


class OrganizationChatSettings(ResponseModel):
    tenant_id: str
    default_agent_id: str | None
    revision: int = Field(ge=0, le=2147483647)
    configured: bool
    can_run: bool
    status: Literal["unconfigured", "unavailable", "disabled", "needs_setup", "unverified", "ready"]


class OrganizationChatSettingsInput(InputModel):
    default_agent_id: str | None = Field(max_length=64)
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)

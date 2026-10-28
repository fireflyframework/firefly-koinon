# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/authorized_applications/dtos.py
SHA256: b81c78f674607894b981725b0598efb191d6e312d07973f5e508b8c3dede60d3

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime

from koinon_sdk._base import ResponseModel


class AuthorizedApplication(ResponseModel):
    id: str
    client_id: str
    name: str
    resource: str
    tenant_id: str
    tenant_name: str
    workspace_id: str
    workspace_name: str
    scopes: list[str]
    status: Literal["active", "expired", "revoked"]
    connected_at: AwareDatetime
    expires_at: AwareDatetime
    last_used_at: AwareDatetime | None
    revoked_at: AwareDatetime | None

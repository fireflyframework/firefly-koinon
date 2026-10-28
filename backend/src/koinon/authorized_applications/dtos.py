# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict


class AuthorizedApplication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
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


def application_dto(row) -> dict:
    fields = {key: getattr(row, key) for key in AuthorizedApplication.model_fields if key != "status"}
    status = "revoked" if row.revoked_at else "expired" if row.expires_at <= datetime.now(UTC) else "active"
    return AuthorizedApplication(**fields, status=status).model_dump(mode="json")

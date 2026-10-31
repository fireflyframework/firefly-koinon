# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/mcp/dtos.py
SHA256: e27bc10bb7e1004361c14dc1f4ef0e79c3cebaa9fb4f242ad1c097a97a422f82

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import ResponseModel
from koinon_sdk.evidence import SourceReference


class Frozen(ResponseModel):
    pass


class McpToolCapability(Frozen):
    name: str
    required_scopes: tuple[str, ...]
    access: Literal["read", "query", "proposal", "app_only"]
    requires_app: bool = False


class McpReviewSupport(Frozen):
    supported: bool
    mechanism: Literal["mcp_apps"] = "mcp_apps"
    resource_uri: Literal["ui://koinon/knowledge-review"] = "ui://koinon/knowledge-review"
    mime_type: Literal["text/html;profile=mcp-app"] = "text/html;profile=mcp-app"
    external_redirect: Literal[False] = False
    client_support: Literal["not_observed"] = "not_observed"


class McpRegisteredClient(Frozen):
    client_id: str
    name: str
    scopes: tuple[str, ...]
    client_auth: Literal["public", "confidential"]


class McpConnectionDescriptor(Frozen):
    enabled: bool
    local_only: bool = False
    endpoint: str | None
    transport: Literal["streamable-http"] = "streamable-http"
    authentication: tuple[Literal["personal_token", "oauth"], ...]
    clients: tuple[McpRegisteredClient, ...] = ()
    oauth_enabled: bool
    oauth_registration: Literal["pre_registered"] | None
    supported_scopes: tuple[str, ...]
    tools: tuple[McpToolCapability, ...]
    review: McpReviewSupport
    client_acceptance: Literal["not_verified"] = "not_verified"


class McpReadReceipt(Frozen):
    status: Literal["recorded", "not_recorded"]
    id: str | None = None
    sha256: str | None = None
    expires_at: AwareDatetime | None = None
    sources: tuple[SourceReference, ...] = Field(default=(), max_length=64)
    reason: (
        Literal[
            "incomplete_or_unsupported_source_manifest",
            "source_manifest_limit_or_missing_revision",
            "receipt_byte_limit",
            "active_receipt_limit",
            "source_reuse_scope_required",
            "capture_unavailable",
            "transitive_lineage_unqualified",
            "catalog_is_not_source_evidence",
        ]
        | None
    ) = None

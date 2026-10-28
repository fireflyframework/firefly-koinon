# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal, TypedDict


class IndexScope(TypedDict):
    workspace_id: str
    domain: Literal["documents", "structured"]


class IndexFilter(IndexScope, total=False):
    limit: int
    offset: int
    status: str
    dimensions: int
    model_id: str
    provider_kind: str


class IdentityFilter(TypedDict, total=False):
    q: str
    kind: Literal["keycloak", "entra", "google_workspace"]
    status: Literal["draft", "configured", "blocked", "verified", "active", "disabled"]
    page: int
    page_size: int


class IdentityGroupFilter(TypedDict, total=False):
    q: str
    limit: int
    after: str


class IdentityMappingFilter(TypedDict, total=False):
    q: str
    status: Literal["all", "enabled", "disabled"]
    workspace_id: str
    page: int
    page_size: int


class AttachmentFilter(TypedDict, total=False):
    q: str
    kind: Literal["document", "image", "bundle"]
    status: Literal["storing", "queued", "extracting", "ready", "failed", "cancelled", "expired", "deleted"]
    page: int
    page_size: int


class AttachmentChunkFilter(TypedDict, total=False):
    q: str
    page: int
    page_size: int


class ExportFilter(TypedDict, total=False):
    q: str
    status: Literal["all", "ready", "cancelled", "expired"]
    page: int
    page_size: int


class ShareFilter(TypedDict, total=False):
    q: str
    status: Literal["all", "active", "revoked", "expired"]
    page: int
    page_size: int

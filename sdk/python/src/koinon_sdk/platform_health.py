# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/platform/dtos.py
SHA256: afc5b34445f22a1c0d86987da89d6063c196e9fa1c75808fc0422e2aa8ee2ba7

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field

from koinon_sdk._base import ResponseModel

HealthComponentId = Literal[
    "database-primary",
    "database-documents",
    "database-documents-control",
    "database-structured",
    "database-structured-control",
    "storage-documents",
    "storage-structured",
    "indexes-documents",
    "indexes-structured",
    "ingestion-documents",
    "ingestion-structured",
    "model-configuration",
    "communications",
    "workers",
]
HealthStatus = Literal["passed", "failed", "unknown", "disabled"]
HealthBasis = Literal["observed", "configuration", "none"]
HealthFreshness = Literal["current", "stale", "unknown"]
HealthCoverage = Literal["complete", "partial", "unavailable"]
HealthReason = Literal[
    "DATABASE_OK",
    "DATABASE_UNAVAILABLE",
    "RUNTIME_ROLE_UNVERIFIED",
    "RUNTIME_ROLE_UNSAFE",
    "MODULE_DISABLED",
    "STORAGE_NOT_PROBED",
    "INDEXES_VERIFIED",
    "INDEXES_INCOMPLETE",
    "INDEXES_NOT_PROBED",
    "NO_INDEXES",
    "INGESTION_STATE_OBSERVED",
    "INGESTION_FAILURES",
    "MODEL_CONFIGURATION_PRESENT",
    "MODEL_CONFIGURATION_INCOMPLETE",
    "PROVIDER_NOT_PROBED",
    "COMMUNICATIONS_DISABLED",
    "COMMUNICATIONS_CONFIGURED",
    "COMMUNICATIONS_INCOMPLETE",
    "WORKER_LIVENESS_UNKNOWN",
    "OBSERVATION_UNAVAILABLE",
    "OBSERVATION_BOUNDED",
    "OBSERVATION_STALE",
]
HealthRemediation = Literal[
    "none",
    "retry_read",
    "review_configuration",
    "review_indexes",
    "review_ingestion",
    "review_communications",
    "review_worker",
]
SystemComponentId = Literal["backend", "documents", "structured", "storage", "python-sdk", "framework"]
SystemDistribution = Literal[
    "firefly-koinon",
    "firefly-koinon-documents",
    "firefly-koinon-structured",
    "firefly-koinon-storage",
    "firefly-koinon-sdk",
    "pyfly",
]
SystemLimitId = Literal[
    "api_capacity",
    "worker_capacity",
    "worker_concurrency",
    "max_index_workspaces",
    "mcp_max_concurrency",
    "mcp_max_request_bytes",
    "mcp_max_response_bytes",
    "ingestion_raw_max_bytes",
    "ingestion_scratch_max_bytes",
    "ingestion_child_rss_max_bytes",
]


class PlatformValue(ResponseModel):
    pass


class HealthCounts(PlatformValue):
    observed_total: int = Field(strict=True, ge=0, le=1000)
    observed_ready: int = Field(default=0, strict=True, ge=0, le=1000)
    observed_pending: int = Field(default=0, strict=True, ge=0, le=1000)
    observed_running: int = Field(default=0, strict=True, ge=0, le=1000)
    observed_failed: int = Field(default=0, strict=True, ge=0, le=1000)


class HealthComponent(PlatformValue):
    id: HealthComponentId
    configured: bool = Field(strict=True)
    status: HealthStatus
    basis: HealthBasis
    freshness: HealthFreshness
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    reason: HealthReason
    remediation: HealthRemediation
    counts: HealthCounts | None = None
    coverage: HealthCoverage


class HealthSummary(PlatformValue):
    passed: int = Field(default=0, strict=True, ge=0, le=16)
    failed: int = Field(default=0, strict=True, ge=0, le=16)
    unknown: int = Field(default=0, strict=True, ge=0, le=16)
    disabled: int = Field(default=0, strict=True, ge=0, le=16)


class PlatformHealth(PlatformValue):
    tenant_id: str = Field(min_length=1, max_length=64)
    checked_at: datetime
    summary: HealthSummary = Field(default_factory=HealthSummary)
    components: list[HealthComponent] = Field(max_length=16)


class SystemComponentVersion(PlatformValue):
    id: SystemComponentId
    distribution: SystemDistribution
    version: str | None = Field(default=None, max_length=64, pattern="^[A-Za-z0-9.!+_-]+$")
    available: bool = Field(strict=True)


class SystemCapabilities(PlatformValue):
    knowledge_enabled: bool = Field(strict=True)
    mcp_enabled: bool = Field(strict=True)
    communications_enabled: bool = Field(strict=True)
    scheduled_consumers_enabled: bool = Field(strict=True)


class SystemLimit(PlatformValue):
    id: SystemLimitId
    value: int = Field(strict=True, ge=0, le=9007199254740991)
    unit: Literal["operations", "bytes", "workspaces"]
    scope: Literal["process", "file"]


class SystemArtifact(PlatformValue):
    component: SystemComponentId
    kind: Literal["license", "notice", "sbom"]
    present: bool | None = Field(default=None, strict=True)
    sha256: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    content_type: Literal["text/plain", "application/json"] | None = None


class SystemInformation(PlatformValue):
    tenant_id: str = Field(min_length=1, max_length=64)
    checked_at: datetime
    product: Literal["koinon"] = "koinon"
    components: list[SystemComponentVersion] = Field(max_length=6)
    serving_role: Literal["api", "worker", "unknown"]
    capabilities: SystemCapabilities
    limits: list[SystemLimit] = Field(max_length=10)
    build_revision: str | None = Field(default=None, pattern="^[a-f0-9]{40}$")
    license_expression: Literal["Apache-2.0"] = "Apache-2.0"
    copyright: Literal["Copyright 2026 Firefly Software Foundation"] = (
        "Copyright 2026 Firefly Software Foundation"
    )
    artifacts: list[SystemArtifact] = Field(max_length=18)

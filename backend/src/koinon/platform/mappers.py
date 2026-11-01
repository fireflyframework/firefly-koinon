# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Finite wire mappings deliberately exclude native diagnostic detail strings."""

from datetime import UTC, datetime, timedelta

from koinon.platform.dtos import (
    HealthBasis,
    HealthComponent,
    HealthComponentId,
    HealthCounts,
    HealthCoverage,
    HealthReason,
    HealthRemediation,
    HealthStatus,
)
from koinon.platform.repositories import StatusWindow


def counts(window: StatusWindow) -> HealthCounts:
    states = [value.lower() for value in window.states]
    return HealthCounts(
        observed_total=len(states),
        observed_ready=sum(
            value in {"ready", "active", "completed", "succeeded", "ingested"} for value in states
        ),
        observed_pending=sum(value in {"pending", "queued", "waiting"} for value in states),
        observed_running=sum(value in {"running", "building", "processing", "indexing"} for value in states),
        observed_failed=sum(value in {"failed", "error", "errored", "dead"} for value in states),
    )


def component(
    identifier: HealthComponentId,
    *,
    configured: bool = True,
    status: HealthStatus = "unknown",
    basis: HealthBasis = "none",
    reason: HealthReason = "OBSERVATION_UNAVAILABLE",
    remediation: HealthRemediation = "retry_read",
    window: StatusWindow | None = None,
    coverage: HealthCoverage = "unavailable",
) -> HealthComponent:
    now = datetime.now(UTC) if basis == "observed" else None
    return HealthComponent(
        id=identifier,
        configured=configured,
        status=status,
        basis=basis,
        freshness="current" if now else "unknown",
        observed_at=now,
        expires_at=now + timedelta(seconds=30) if now else None,
        reason=reason,
        remediation=remediation,
        counts=counts(window) if window else None,
        coverage=("complete" if window.complete else "partial") if window else coverage,
    )

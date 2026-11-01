# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from koinon.platform.dtos import HealthComponent, HealthCounts, PlatformHealth


def component(**changes):
    now = datetime.now(UTC)
    return dict(
        id="database-primary",
        configured=True,
        status="passed",
        basis="observed",
        freshness="current",
        observed_at=now,
        expires_at=now + timedelta(seconds=30),
        reason="DATABASE_OK",
        remediation="none",
        coverage="complete",
        **changes,
    )


def test_passed_health_requires_current_positive_observation():
    assert HealthComponent(**component()).status == "passed"
    for changes in (
        {"basis": "configuration"},
        {"freshness": "stale"},
        {"observed_at": None},
        {"expires_at": None},
    ):
        values = component()
        values.update(changes)
        with pytest.raises(ValidationError):
            HealthComponent(**values)


def test_bounded_counts_are_explicitly_observed_and_never_invent_a_total():
    values = HealthCounts(
        observed_total=5, observed_ready=2, observed_pending=1, observed_running=1, observed_failed=1
    )
    assert "total" not in values.model_dump()
    for invalid in (True, -1, 1001):
        with pytest.raises(ValidationError):
            HealthCounts(observed_total=invalid)


def test_wire_output_forbids_unreviewed_diagnostics_and_derives_separate_counts():
    item = HealthComponent(**component())
    result = PlatformHealth(tenant_id="tenant", checked_at=datetime.now(UTC), components=[item])
    assert result.summary.passed == 1
    assert not hasattr(result, "overall_available")
    with pytest.raises(ValidationError):
        HealthComponent(**component(), raw_error="postgresql://secret@internal.example/private")


def test_unknown_artifact_has_no_invented_presence_digest_or_path():
    from koinon.platform.dtos import SystemArtifact

    artifact = SystemArtifact(component="backend", kind="sbom", present=None)
    assert artifact.sha256 is None
    with pytest.raises(ValidationError):
        SystemArtifact(component="backend", kind="license", present=True)
    with pytest.raises(ValidationError):
        SystemArtifact(component="backend", kind="license", present=False, sha256="a" * 64)

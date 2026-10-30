# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One immutable PII policy shared by standalone and versioned source processing."""

from dataclasses import dataclass

from flycanon.config import CanonSettings
from flycanon.core.services.pii import PiiPolicy, PiiScanner, build_pii_scanner


@dataclass(frozen=True)
class SourceIntakePolicy:
    value: PiiPolicy
    scanner: PiiScanner | None


def build_intake_policy(settings: CanonSettings) -> SourceIntakePolicy:
    try:
        policy = PiiPolicy(settings.pii_policy)
    except ValueError:
        policy = PiiPolicy.warn
    scanner = build_pii_scanner(settings.pii_scanner) if policy != PiiPolicy.disabled else None
    return SourceIntakePolicy(policy, scanner)

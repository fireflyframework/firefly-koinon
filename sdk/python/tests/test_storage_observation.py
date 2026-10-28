# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon_sdk.attachments import AttachmentObservation


def test_old_observation_defaults_to_unconfigured_and_unknown_health_stays_unknown():
    legacy = AttachmentObservation(available=True, reason="Checked")
    assert legacy.configured is False
    remote = AttachmentObservation(available=None, reason="Provider unverified", configured=True)
    assert remote.available is None and remote.configured is True

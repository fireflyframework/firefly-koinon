# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""No-send dependency for transactional tests; this is not provider acceptance evidence."""

from types import SimpleNamespace

from pyfly.kernel import ServiceUnavailableException


class OwnedReadiness:
    state = "ready"

    def observe(self, **kwargs):
        return SimpleNamespace(state=self.state, sender_address="team@example.test")

    def require_ready(self, **kwargs):
        if self.state != "ready":
            raise ServiceUnavailableException("Fixture email is disabled", code="COMMUNICATIONS_NOT_READY")
        return self.observe()

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure bounded fingerprinting of one primary-database authority observation."""

import json
from collections.abc import Sequence
from hashlib import sha256

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.release_dtos import CuratedReleaseStamp

MAX_ROWS = 8192
MAX_BYTES = 8 * 1024 * 1024


def release_stamp(
    subject: str, tenant_id: str, token_id: str | None, rows: Sequence[tuple]
) -> CuratedReleaseStamp:
    if len(rows) > MAX_ROWS:
        raise AccessDenied("Narrow the selected knowledge scope", code="KNOWLEDGE_SCOPE_TOO_WIDE")
    encoded = sorted(json.dumps(tuple(row), ensure_ascii=False, separators=(",", ":")) for row in rows)
    payload = "\n".join(encoded).encode()
    if len(payload) > MAX_BYTES:
        raise AccessDenied("Narrow the selected knowledge scope", code="KNOWLEDGE_SCOPE_TOO_WIDE")
    identity = json.dumps([subject, tenant_id, token_id], separators=(",", ":")).encode()
    return CuratedReleaseStamp(sha256(identity).hexdigest(), sha256(payload).hexdigest(), len(rows))

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from uuid import uuid4


def identifier() -> str:
    return str(uuid4())


def timestamp() -> datetime:
    return datetime.now(UTC)

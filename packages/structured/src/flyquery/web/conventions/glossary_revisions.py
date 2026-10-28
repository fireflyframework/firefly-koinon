# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from starlette.requests import Request

from flyquery.web.conventions.exceptions import InvalidRequest


def expected_glossary_revision(request: Request) -> datetime | None:
    value = request.headers.get("if-match")
    if value is None:
        return None
    try:
        value = value.strip()
        if len(value) > 128 or value.startswith("W/") or value == "*":
            raise ValueError
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        revision = datetime.fromisoformat(value)
        if revision.tzinfo is None:
            raise ValueError
        return revision
    except ValueError as error:
        raise InvalidRequest(
            "If-Match must contain the exact current updated_at timestamp with a timezone"
        ) from error

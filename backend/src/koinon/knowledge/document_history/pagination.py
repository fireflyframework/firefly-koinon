# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared bounded history page validation."""

from pyfly.kernel import InvalidRequestException


def pagination(page, page_size):
    if (
        type(page) is not int
        or type(page_size) is not int
        or page < 1
        or not 1 <= page_size <= 100
        or (page - 1) * page_size > 100_000
    ):
        raise InvalidRequestException("Choose a valid page and page size up to 100", code="INVALID_PAGE")

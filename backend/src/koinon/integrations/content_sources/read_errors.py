# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Use the same sanitized source failures on every protected product surface."""

from pyfly.kernel.exceptions import PyFlyException
from pyfly.web.adapters.starlette.errors import global_exception_handler
from starlette.requests import Request
from starlette.responses import Response

from koinon.integrations.content_sources.controllers import _safe


async def source_problem(request: Request, error: Exception) -> Response:
    async def failed():
        raise error

    try:
        await _safe(failed())
    except PyFlyException as problem:
        return await global_exception_handler(request, problem)
    raise RuntimeError("Source error translation returned without raising a problem")

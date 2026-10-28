# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preserve typed domain denials without changing common API error handlers."""

from importlib import import_module
from importlib.util import find_spec
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse


async def domain_problem(request: Request, exception: Any) -> JSONResponse:
    return JSONResponse(
        {
            "type": exception.type_uri,
            "title": exception.title,
            "status": exception.status,
            "code": exception.code,
            "detail": exception.detail,
            "instance": exception.instance or request.url.path,
            "errors": exception.errors,
        },
        status_code=exception.status,
        media_type="application/problem+json",
    )


def register_domain_problems(app):
    for package in ("flycanon", "flyquery"):
        if find_spec(package) is not None:
            error = import_module(package + ".web.conventions.exceptions").FireflyHTTPException
            app.add_exception_handler(error, domain_problem)

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import component
from pyfly.web.filters import OncePerRequestFilter
from pyfly.web.ports.filter import CallNext
from starlette.requests import Request
from starlette.responses import Response


@component(name="knowledge.bulk.private_responses")
class PrivateBulkResponses(OncePerRequestFilter):
    url_patterns = [
        "/api/v1/tenants/*/sources/batches*",
        "/bff/api/v1/tenants/*/sources/batches*",
        "/api/v1/tenants/*/source-batch-capabilities*",
        "/bff/api/v1/tenants/*/source-batch-capabilities*",
        "/api/v1/tenants/*/queries/batches*",
        "/bff/api/v1/tenants/*/queries/batches*",
        "/api/v1/tenants/*/query-batch-capabilities*",
        "/bff/api/v1/tenants/*/query-batch-capabilities*",
    ]

    async def do_filter(self, request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)
        response.headers["Cache-Control"] = "private, no-store"
        vary = [value.strip() for value in response.headers.get("Vary", "").split(",") if value.strip()]
        for name in ["Cookie", "Authorization"]:
            if name.lower() not in {value.lower() for value in vary}:
                vary.append(name)
        response.headers["Vary"] = ", ".join(vary)
        return response

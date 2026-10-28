# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel
from starlette.responses import JSONResponse


def private_json(value: BaseModel, *, status=200) -> JSONResponse:
    return JSONResponse(
        value.model_dump(mode="json"),
        status_code=status,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )

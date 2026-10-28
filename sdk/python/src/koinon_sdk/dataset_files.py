# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import Field

from koinon_sdk._base import ResponseModel


class DatasetFileAppendResult(ResponseModel):
    dataset_id: str
    file_version_id: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1)
    table_ids: list[str] = Field(min_length=1, max_length=128)
    status: Literal["ready"]

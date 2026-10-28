# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentRevisionPreconditions(InputModel):
    expected_source_version_id: UUID | None = None
    expected_extraction_id: UUID | None = None

    @model_validator(mode="after")
    def paired(self) -> "DocumentRevisionPreconditions":
        if (self.expected_source_version_id is None) != (self.expected_extraction_id is None):
            raise ValueError("Supply the exact source version and extraction together")
        return self

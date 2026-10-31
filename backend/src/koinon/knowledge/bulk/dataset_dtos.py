# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pyfly.kernel import ConflictException


class DatasetReservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    native_dataset_id: UUID
    native_file_id: UUID
    catalog_file_version_id: str = Field(min_length=1, max_length=64)
    max_tables: int = Field(default=16, ge=1, le=16, strict=True)

    @classmethod
    def stored(cls, value: object) -> "DatasetReservation":
        try:
            return cls.model_validate(value)
        except ValidationError:
            raise ConflictException(
                "Stored dataset reservation cannot be verified", code="BULK_NATIVE_RECEIPT_CONFLICT"
            ) from None

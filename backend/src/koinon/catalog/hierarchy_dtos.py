# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class CatalogMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    parent_id: str = Field(min_length=1, max_length=64)
    expected_parent_id: str = Field(min_length=1, max_length=64)
    expected_updated_at: AwareDatetime

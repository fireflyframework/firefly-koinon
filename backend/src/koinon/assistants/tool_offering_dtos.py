# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Internal model-input contracts; source labels are data, never authority."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from koinon.assistants.tool_activity import ToolName


class SelectedSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    asset_id: str = Field(min_length=1, max_length=64)
    kind: Literal["document", "dataset", "knowledge_item"]
    name: str = Field(min_length=1, max_length=255)


class ToolOffering(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    selection: Literal["explicit_selection", "broader_scope", "private_attachments"]
    sources: tuple[SelectedSource, ...] = Field(default=(), max_length=128)
    tools: tuple[ToolName, ...] = Field(default=(), max_length=5)

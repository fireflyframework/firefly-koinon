# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Trusted server configuration for help; never organization source evidence."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from koinon.assistants.tool_activity import ToolName

HelpTopic = Literal["identity", "capabilities", "identity_and_capabilities", "navigation"]


class ProductHelpContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: Literal["product_configuration"] = "product_configuration"
    product_name: str = Field(min_length=1, max_length=120)
    assistant_name: str = Field(min_length=1, max_length=120)
    branding_revision: int = Field(ge=0)
    branding_origin: Literal["organization", "deployment"] = "deployment"
    selection: Literal["explicit_selection", "broader_scope", "private_attachments"] = "broader_scope"
    tools: tuple[ToolName, ...] = Field(default=(), max_length=5)

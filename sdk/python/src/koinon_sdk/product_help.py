# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/answers/help_dtos.py
SHA256: 82146745c76f3729cd0d33c76468171ed5dc6dba12fda73e416ef8c5fa8eaa69

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import Field

from koinon_sdk._base import ResponseModel

ToolName = Literal[
    "search_knowledge",
    "inspect_schema",
    "query_dataset",
    "propose_catalog_update",
    "search_private_attachments",
]
HelpTopic = Literal["identity", "capabilities", "identity_and_capabilities", "navigation"]


class ProductHelpContext(ResponseModel):
    kind: Literal["product_configuration"] = "product_configuration"
    product_name: str = Field(min_length=1, max_length=120)
    assistant_name: str = Field(min_length=1, max_length=120)
    branding_revision: int = Field(ge=0)
    branding_origin: Literal["organization", "deployment"] = "deployment"
    selection: Literal["explicit_selection", "broader_scope", "private_attachments"] = "broader_scope"
    tools: tuple[ToolName, ...] = Field(default=(), max_length=5)

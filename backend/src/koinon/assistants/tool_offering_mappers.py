# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded source metadata for model instructions, separate from authorization."""

from koinon.assistants.tool_offering_dtos import SelectedSource, ToolOffering
from koinon.catalog.entities import CatalogEntry
from koinon.knowledge.attachments.ports import AttachmentRef


def selected_source(entry: CatalogEntry) -> SelectedSource:
    return SelectedSource.model_validate({"asset_id": entry.id, "kind": entry.kind, "name": entry.name})


def source_context(offering: ToolOffering) -> str:
    return offering.model_dump_json()


def private_offering(refs: tuple[AttachmentRef, ...], *, search_enabled: bool) -> ToolOffering:
    return ToolOffering(
        selection="private_attachments",
        tools=("search_private_attachments",)
        if search_enabled and any(ref.kind != "image" for ref in refs)
        else (),
    )

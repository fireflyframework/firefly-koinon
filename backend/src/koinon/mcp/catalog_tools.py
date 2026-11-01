# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fixed user-requested organization operations retain canonical policy and stale-state guards."""

from typing import TYPE_CHECKING, Annotated, Any, Literal

from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from koinon.catalog.hierarchy_dtos import CatalogMove
from koinon.knowledge.availability.dtos import AvailabilityRequest

if TYPE_CHECKING:
    from pyfly.mcp import McpServer

    from koinon.mcp.server import CanonicalDispatcher

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
WRITE_SCOPES = ("catalog:read", "catalog:write")
CREATE_UNKNOWN = (
    "The folder creation outcome is unknown. Do not repeat the create request; "
    "inspect the authorized parent and recorded activity before deciding what to do next."
)


class CatalogOrganizationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    metadata: dict[str, JsonValue] | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def changes_present(self):
        if self.name is None and self.description is None and self.metadata is None:
            raise ValueError("Provide the exact organizational fields to change")
        return self


def register_catalog_tools(server: "McpServer", api: "CanonicalDispatcher", *, oauth_enabled: bool) -> None:
    organization = ToolAnnotations(
        read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
    )
    read = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )

    def metadata(scopes=WRITE_SCOPES):
        return {"securitySchemes": [{"type": "oauth2", "scopes": list(scopes)}]} if oauth_enabled else None

    @server.tool(annotations=organization, structured_output=True, meta=metadata())
    async def koinon_create_folder(
        tenant_id: Identifier,
        kind: Literal["workspace", "project", "collection", "corpus"],
        name: Annotated[str, Field(min_length=1, max_length=255)],
        ctx: Context,
        parent_id: Identifier | None = None,
        description: Annotated[str, Field(max_length=4000)] = "",
    ) -> dict[str, Any]:
        """Create the exact organizational folder requested by the user, within current authority.

        This does not publish knowledge content. Creation is one attempt, without a replay receipt.
        If its outcome is unknown, inspect the parent before another decision; never retry automatically.
        """
        return await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/catalog",
            body={"kind": kind, "name": name, "parent_id": parent_id, "description": description},
            required_scopes=WRITE_SCOPES,
            expected_status=(201,),
            unknown_outcome_message=CREATE_UNKNOWN,
        )

    @server.tool(annotations=organization, structured_output=True, meta=metadata())
    async def koinon_update_catalog(
        tenant_id: Identifier,
        entry_id: Identifier,
        expected_updated_at: AwareDatetime,
        changes: CatalogOrganizationPatch,
        ctx: Context,
    ) -> dict[str, Any]:
        """Apply user-requested names, descriptions or public metadata against the exact fetched timestamp.

        Metadata replaces current public metadata: preserve intended existing fields, including tags.
        This cannot update AI-derived knowledge content, ancestry, status or permissions.
        """
        return await api.call(
            ctx,
            "PATCH",
            f"/api/v1/tenants/{tenant_id}/catalog/{entry_id}",
            body={
                **changes.model_dump(mode="json", exclude_none=True),
                "expected_updated_at": expected_updated_at.isoformat(),
            },
            required_scopes=WRITE_SCOPES,
        )

    @server.tool(annotations=organization, structured_output=True, meta=metadata())
    async def koinon_move_folder(
        tenant_id: Identifier,
        entry_id: Identifier,
        move: CatalogMove,
        ctx: Context,
    ) -> dict[str, Any]:
        """Move a user-selected collection or corpus within its project using exact parent/time preconditions.

        Native cycle, busy-descendant, protected-root and source/destination access checks remain mandatory.
        """
        return await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/catalog/{entry_id}/move",
            body=move.model_dump(mode="json"),
            required_scopes=WRITE_SCOPES,
        )

    @server.tool(annotations=organization, structured_output=True, meta=metadata())
    async def koinon_archive_catalog(
        tenant_id: Identifier,
        entry_id: Identifier,
        expected_updated_at: AwareDatetime,
        ctx: Context,
    ) -> dict[str, Any]:
        """Recoverably archive the exact user-selected catalog entry; never permanently deletes it."""
        return await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/catalog/{entry_id}/archive",
            params={"expected_updated_at": expected_updated_at.isoformat()},
            required_scopes=WRITE_SCOPES,
        )

    @server.tool(annotations=organization, structured_output=True, meta=metadata())
    async def koinon_restore_catalog(
        tenant_id: Identifier,
        entry_id: Identifier,
        expected_updated_at: AwareDatetime,
        ctx: Context,
    ) -> dict[str, Any]:
        """Restore the selected archived entry with current authority and exact timestamp preconditions."""
        return await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/catalog/{entry_id}/restore",
            params={"expected_updated_at": expected_updated_at.isoformat()},
            required_scopes=WRITE_SCOPES,
        )

    @server.tool(annotations=read, structured_output=True, meta=metadata(("catalog:read",)))
    async def koinon_availability(
        tenant_id: Identifier,
        selection: AvailabilityRequest,
        ctx: Context,
    ) -> dict[str, Any]:
        """Observe current read/search/query availability of selected assets; never starts processing."""
        return await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/catalog/availability",
            body=selection.model_dump(mode="json", exclude_none=True),
        )

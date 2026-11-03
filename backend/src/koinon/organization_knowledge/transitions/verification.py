# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Fresh paged metadata validation immediately before the settings CAS."""

from collections import defaultdict
from dataclasses import dataclass

from pyfly.container import service
from pyfly.kernel import ConflictException

from koinon.knowledge.indexes.adapters import NativeIndexAdapter
from koinon.organization_knowledge.transitions.discovery import ModeDiscovery
from koinon.organization_knowledge.transitions.document_views import ModeDocumentViews
from koinon.organization_knowledge.transitions.readiness import ModeRoleReadiness
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository


@dataclass(frozen=True)
class VerificationPage:
    after: str | None
    scanned: int
    complete: bool
    counts: dict[str, int]


class WorkspacePreparationRequired(ConflictException):
    def __init__(self, workspace_id, *, code, target_id=None, repairable=True):
        super().__init__("Current workspace preparation is required", code=code)
        self.workspace_id, self.target_id, self.repairable = workspace_id, target_id, repairable


@service(name="organization_knowledge.mode_verification")
class ModeVerification:
    def __init__(
        self,
        discovery: ModeDiscovery,
        targets: ModeTargetRepository,
        roles: ModeRoleReadiness,
        views: ModeDocumentViews,
        indexes: NativeIndexAdapter,
    ):
        self.discovery, self.targets, self.roles = discovery, targets, roles
        self.views, self.indexes = views, indexes

    async def page(
        self, transition, *, after=None, page_size=100, workspace_id=None, native_workspace_id=None
    ):
        entries, observed = await self.discovery.page(
            transition,
            after=after,
            page_size=page_size,
            workspace_id=workspace_id,
            native_workspace_id=native_workspace_id,
        )
        rows = await self.targets.selected(
            transition.tenant_id, transition.id, [value["id"] for value in observed]
        )
        mode = transition.requested_settings["documents"]["answer_mode"]
        counts = {"verified_documents": 0, "verified_workspaces": 0, "verified_curated": 0}
        documents = defaultdict(list)
        for value in observed:
            target = rows.get(value["id"])
            if (
                target is None
                or target.status == "excluded"
                or any(
                    getattr(target, key) != value[key]
                    for key in ("catalog_id", "workspace_id", "native_id", "native_workspace_id", "kind")
                )
            ):
                raise WorkspacePreparationRequired(
                    value["workspace_id"],
                    code="KNOWLEDGE_MODE_SCOPE_CHANGED",
                )
            if target.kind == "workspace":
                try:
                    await self.workspace(transition, target, mode, lock=False)
                except ConflictException as error:
                    raise WorkspacePreparationRequired(
                        target.workspace_id, code=error.code, target_id=target.id
                    ) from error
                counts["verified_workspaces"] += 1
            elif target.kind == "curated":
                if mode == "rlm":
                    raise ConflictException(
                        "RLM is not qualified for curated knowledge", code="KNOWLEDGE_RLM_UNQUALIFIED"
                    )
                counts["verified_curated"] += 1
            else:
                documents[target.native_workspace_id].append(target)
                counts["verified_documents"] += 1
        for workspace_id, targets in documents.items():
            scope = dict(tenant_id=transition.tenant_id, workspace_id=workspace_id, actor=transition.actor)
            try:
                await self.views.verify_sources(**scope, source_ids=[target.native_id for target in targets])
            except ConflictException as error:
                target = next(
                    (target for target in targets if target.native_id == error.context.get("source_id")), None
                )
                if target is None:
                    raise
                raise WorkspacePreparationRequired(
                    target.workspace_id, code=error.code, target_id=target.id, repairable=False
                ) from error
            if mode == "rlm":
                pending = next((target for target in targets if target.status != "ready"), None)
                if pending:
                    raise WorkspacePreparationRequired(
                        pending.workspace_id, target_id=pending.id, code="RLM_DOCUMENT_VIEWS_REQUIRED"
                    )
                try:
                    await self.views.verify_pins(
                        **scope, pins=[{**target.result, "source_id": target.native_id} for target in targets]
                    )
                except ConflictException as error:
                    target = next(
                        (target for target in targets if target.native_id == error.context.get("source_id")),
                        None,
                    )
                    if target is None:
                        raise
                    raise WorkspacePreparationRequired(
                        target.workspace_id, code=error.code, target_id=target.id
                    ) from error
        return VerificationPage(
            entries[-1].id if entries else after, len(entries), len(entries) < page_size, counts
        )

    async def workspace(self, transition, target, mode, *, lock=True):
        roles = await self.roles.check(
            transition.actor,
            transition.tenant_id,
            target.workspace_id,
            mode,
            has_documents=target.result.get("has_documents", False),
            lock=lock,
        )
        if target.status not in {"prepared", "ready"} or roles != target.result.get("roles"):
            raise ConflictException(
                "A selected model connection changed after preflight",
                code="KNOWLEDGE_MODE_DEPENDENCY_CHANGED",
            )
        if mode != "rag" or not target.result.get("has_documents"):
            return
        identifier = target.result.get("index_id")
        actual = (
            await self.indexes.get_native(
                tenant_id=transition.tenant_id,
                native_workspace_id=target.native_workspace_id,
                catalog_workspace_id=target.workspace_id,
                domain="documents",
                actor=transition.actor,
                identifier=identifier,
            )
            if identifier
            else None
        )
        if (
            not actual
            or not actual["active"]
            or not actual["indexed"]
            or actual["chunk_count"] != actual["vector_count"]
            or actual["space_id"] != roles["documents.embedding"]["space_id"]
        ):
            raise ConflictException(
                "The selected document index is not active with complete qualified coverage",
                code="KNOWLEDGE_MODE_INDEX_NOT_READY",
            )

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import service

from koinon.knowledge.availability.adapter import NativeAvailabilityAdapter
from koinon.knowledge.availability.dtos import AssetAvailability, AvailabilityRequest, AvailabilityResponse
from koinon.knowledge.availability.repository import AvailabilityRepository
from koinon.knowledge.service import KnowledgeFacade
from koinon.security.authority import primary_authority


@service(name="knowledge.availability")
class KnowledgeAvailabilityService:
    def __init__(
        self, knowledge: KnowledgeFacade, records: AvailabilityRepository, native: NativeAvailabilityAdapter
    ):
        self.knowledge, self.records, self.native = knowledge, records, native

    async def _snapshot(self, subject, tenant_id, identifiers, workspace_id=None):
        async with primary_authority(fresh=True):
            entries = [
                (await self.knowledge._chain(subject, tenant_id, identifier))[0] for identifier in identifiers
            ]
            if workspace_id is not None and any(entry.workspace_id != workspace_id for entry in entries):
                from koinon.catalog.errors import AccessDenied

                raise AccessDenied("Selected assets disagree with the workspace", code="INVALID_WORKSPACE")
            return await self.records.load(tenant_id, entries)

    async def observe(self, subject: str, tenant_id: str, data: AvailabilityRequest) -> AvailabilityResponse:
        before = await self._snapshot(subject, tenant_id, data.asset_ids, data.workspace_id)
        first = await self.native.observe(subject, tenant_id, before)
        second = await self.native.observe(subject, tenant_id, before)
        after = await self._snapshot(subject, tenant_id, data.asset_ids, data.workspace_id)
        items = {}
        for identifier, selected in before.items():
            current = after.get(identifier)
            observed = first.get(identifier)
            if current != selected or observed != second.get(identifier):
                items[identifier] = AssetAvailability.model_validate(
                    {
                        key: {"state": "unknown", "reason": "OBSERVATION_CHANGED"}
                        for key in ("read", "search", "query")
                    }
                )
                continue
            value = (
                {key: observed[key] for key in ("read", "search", "query", "revision")} if observed else {}
            )
            phase = selected["phase"]
            if phase == "unknown" and observed:
                phase = observed.get("phase", "unknown")
            if (
                observed
                and observed["read"]["state"] == "ready"
                and observed["search"]["state"] != "ready"
                and selected.get("index_phase") in {"queued", "indexing"}
            ):
                phase = selected["index_phase"]
                value["search"] = {"state": "pending", "reason": "INDEX_WORK_RECORDED"}
            attempt = selected["latest_attempt"]
            if (
                phase == "unknown"
                and observed
                and any(observed[key]["state"] == "ready" for key in ("read", "query"))
            ):
                phase = "complete"
            if attempt is not None and (attempt["state"] != "complete" or phase == "unknown"):
                phase = attempt["state"]
            if selected["blocked"] and selected["kind"] in {"dataset", "table"}:
                value["query"] = {"state": "pending", "reason": "INTAKE_NOT_COMPLETE"}
                if phase == "complete":
                    phase = "unknown"
            items[identifier] = AssetAvailability.model_validate(
                {**value, "phase": phase, "latest_attempt": attempt}
            )
        return AvailabilityResponse(observed_at=datetime.now(UTC), items=items)

    async def processing(self, subject, tenant_id, data):
        from koinon.catalog.errors import AccessDenied
        from koinon.knowledge.availability.dtos import ProcessingActivity, ProcessingResponse

        async with primary_authority(fresh=True):
            await self.knowledge.catalog.authorize(subject, tenant_id, "jobs:manage", data.workspace_id)
            if self.knowledge.catalog.restriction:
                grant = await self.knowledge.catalog.restriction.grant(subject)
                if grant and grant.asset_ids is not None:
                    raise AccessDenied(
                        "Processing history requires a complete workspace", code="TOKEN_SCOPE_DENIED"
                    )
            rows = await self.records.processing(tenant_id, data.workspace_id, data.page, data.page_size)
            visible = []
            for row in rows[: data.page_size]:
                try:
                    await self.knowledge._chain(subject, tenant_id, row["resource_id"])
                except AccessDenied:
                    continue
                visible.append(dict(row))
        observed = (
            (
                await self.observe(
                    subject,
                    tenant_id,
                    AvailabilityRequest(asset_ids=list(dict.fromkeys(row["resource_id"] for row in visible))),
                )
            )
            if visible
            else AvailabilityResponse(observed_at=datetime.now(UTC), items={})
        )
        async with primary_authority(fresh=True):
            await self.knowledge.catalog.authorize(subject, tenant_id, "jobs:manage", data.workspace_id)
            for row in visible:
                await self.knowledge._chain(subject, tenant_id, row["resource_id"])
        return ProcessingResponse(
            observed_at=observed.observed_at,
            next_page=data.page + 1 if len(rows) > data.page_size else None,
            items=[
                ProcessingActivity.model_validate(
                    dict(
                        id=row["id"],
                        resource_id=row["resource_id"],
                        operation=row["operation"],
                        state={
                            "complete": "complete",
                            "error": "failed",
                            "succeeded": "complete",
                            "failed": "failed",
                            "cancelled": "cancelled",
                            "queued": "queued",
                        }.get(row["status"], "unknown"),
                        updated_at=row["updated_at"],
                        availability=observed.items[row["resource_id"]],
                    )
                )
                for row in visible
            ],
        )

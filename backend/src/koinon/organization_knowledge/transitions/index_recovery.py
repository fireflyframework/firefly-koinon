# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Observe an admitted activation without repeating its build or native switch."""

from pyfly.container import service
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy.exc import SQLAlchemyError

from koinon.knowledge.indexes.adapters import index_id
from koinon.knowledge.indexes.lifecycle import IndexLifecycleService


@service(name="organization_knowledge.mode_index_recovery")
class ModeIndexRecoveryService:
    def __init__(self, lifecycle: IndexLifecycleService):
        self.lifecycle = lifecycle

    async def inspect(self, subject, tenant_id, identifier):
        row = await self.lifecycle.scoped(subject, tenant_id, identifier)
        reader = self.lifecycle.reader
        workspace = await reader.authority(subject, tenant_id, row.workspace_id)
        await reader.facade.catalog.authorize(subject, tenant_id, "indexes:manage", row.workspace_id)
        if reader.facade.catalog.restriction:
            await reader.facade.catalog.restriction.resource(subject, workspace, write=True)
        await reader.connections.authority(subject, tenant_id, row.workspace_id)
        selected = await reader.connections.selected(
            tenant_id, row.workspace_id, row.domain, row.domain + ".embedding"
        )
        result = {
            "native_pointer_state": "unavailable",
            "actions": [],
            "expected_revision": row.revision,
            "expected_connection_revision": selected.revision if selected else None,
            "expected_active_id": None,
        }
        try:
            observed = await reader.adapter.overview(
                tenant_id=tenant_id,
                workspace_id=row.native_workspace_id,
                domain=row.domain,
                actor=subject,
            )
        except (RuntimeError, SQLAlchemyError, ServiceUnavailableException):
            return result
        active = observed["active_native_id"]
        result["expected_active_id"] = (
            index_id(tenant_id, row.workspace_id, row.domain, active) if active else None
        )
        pointer = (
            "target"
            if active == row.native_id
            else "previous"
            if active == row.transition.get("previous_native_id")
            else "other"
        )
        result["native_pointer_state"] = pointer
        if row.status == "activating":
            if pointer == "target":
                result["actions"] = ["finish", "restore_previous"]
            elif pointer == "previous":
                result["actions"] = ["restore_previous"]
        return result

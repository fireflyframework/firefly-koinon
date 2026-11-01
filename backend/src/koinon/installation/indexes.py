# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only empty, installation-owned spaces may receive an initial serving index."""

from hashlib import sha256
from json import dumps

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional

from koinon.installation.authority import ACTOR, InstallationAdmissions, InstallationError, InstallationPermit
from koinon.installation.dtos import IndexInstallation
from koinon.installation.writes import NativeInstallationWrites, resource_id
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.connections.dtos import ConnectionInput
from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.adapters import index_id
from koinon.knowledge.indexes.dtos import IndexPlanInput
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.knowledge.indexes.service import KnowledgeIndexService


@service(name="installation.indexes")
class NativeInstallationIndexes:
    def __init__(self, admissions: InstallationAdmissions, reader: Provider[KnowledgeIndexService]):
        self.admissions, self.reader = admissions, reader

    async def owned(self, permit, value):
        run = await self.admissions.require(permit)
        reader = self.reader.get()
        await reader.facade.catalog._lock_tenant(permit.tenant_id)
        identifier = NativeInstallationWrites.reference(run, "index-intent", value.key)
        row = await reader.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != permit.tenant_id or row.created_by != ACTOR:
            raise InstallationError("INSTALLATION_INDEX_CHANGED")
        expected_key = next(
            key + ":" + value.key
            for key in (
                "index-active",
                "index-ready",
                "index-created",
                "index-intent-reconciled",
                "index-intent",
            )
            if key + ":" + value.key in run.checkpoints
        )
        expected = run.checkpoints[expected_key]
        if row.revision != expected["revision"] or row.status != expected["row_status"]:
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        if (
            row.workspace_id,
            row.native_workspace_id,
            row.domain,
            row.provider_id,
            row.model_id,
            row.dimensions,
        ) != (
            NativeInstallationWrites.reference(run, "catalog", value.workspace_key),
            NativeInstallationWrites.reference(run, "catalog", value.workspace_key),
            value.domain,
            NativeInstallationWrites.reference(run, "provider", value.provider_key),
            value.model_id,
            value.dimensions,
        ):
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        provider = await reader.planner.provider(permit.tenant_id, row.provider_id, row.model_id)
        if (
            provider.revision != row.provider_revision
            or embedding_fingerprint(provider, row.model_id, row.dimensions, row.storage_dimensions)
            != row.embedding_fingerprint
        ):
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        if expected_key == "index-intent-reconciled:" + value.key:
            from koinon.installation.intent_recovery import validate_reconciled

            validate_reconciled(permit, value, run, row, provider)
        return run, reader, row, provider

    @transactional(read_from_primary=True)
    async def intent(self, permit: InstallationPermit, value: IndexInstallation):
        run = await self.admissions.require(permit)
        if "index-intent:" + value.key in run.checkpoints:
            if (
                run.checkpoints["index-intent:" + value.key].get("revision") is None
                and "index-intent-reconciled:" + value.key not in run.checkpoints
            ):
                await self.reconcile_intent(permit, value, run)
            return (await self.owned(permit, value))[2].id
        reader = self.reader.get()
        await reader.facade.catalog._lock_tenant(permit.tenant_id)
        workspace_id = NativeInstallationWrites.reference(run, "catalog", value.workspace_key)
        workspace = await reader.facade.catalog.catalog_repository.find_by_id(
            workspace_id, lock=LockMode.PESSIMISTIC_READ
        )
        if (
            workspace is None
            or workspace.tenant_id != permit.tenant_id
            or workspace.kind != "workspace"
            or workspace.status == "archived"
            or workspace.installation_run_id != permit.run_id
        ):
            raise InstallationError("INSTALLATION_WORKSPACE_CHANGED")
        if await reader.records.find_all(
            tenant_id=permit.tenant_id, workspace_id=workspace_id, domain=value.domain
        ) or await reader.connections.selected(
            permit.tenant_id, workspace_id, value.domain, value.domain + ".embedding"
        ):
            raise InstallationError("INSTALLATION_INDEX_EXISTS")
        provider_id = NativeInstallationWrites.reference(run, "provider", value.provider_key)
        provider, profile = await reader.planner.prepare(
            permit.tenant_id,
            IndexPlanInput(
                workspace_id=workspace_id,
                domain=value.domain,
                provider_id=provider_id,
                model_id=value.model_id,
                expected_dimensions=value.dimensions,
            ),
        )
        native_id = ("es-" if value.domain == "documents" else "fs-") + resource_id(
            permit, "index:" + value.key
        ).replace("-", "")
        identifier = index_id(permit.tenant_id, workspace_id, value.domain, native_id)
        slot = sha256(dumps([permit.tenant_id, value.domain, workspace_id]).encode()).hexdigest()
        row = KnowledgeIndex(
            id=identifier,
            tenant_id=permit.tenant_id,
            workspace_id=workspace_id,
            native_workspace_id=workspace_id,
            native_id=native_id,
            domain=value.domain,
            provider_id=provider.id,
            provider_kind=provider.kind,
            provider_revision=provider.revision,
            model_id=value.model_id,
            dimensions=profile["dimensions"],
            storage_dimensions=profile["storage_dimensions"],
            embedding_fingerprint=embedding_fingerprint(
                provider, value.model_id, profile["dimensions"], profile["storage_dimensions"]
            ),
            build_slot=slot,
            status="queued",
            cursor={},
            transition={},
            created_by=ACTOR,
            updated_by=ACTOR,
        )
        row = await reader.records.save(row)
        await reader.facade.catalog._audit(
            ACTOR, permit.tenant_id, "installation.index.intent", identifier, {"run_id": permit.run_id}
        )
        await self.admissions.checkpoint(
            permit,
            "index-intent:" + value.key,
            {
                "status": "done",
                "resource_id": identifier,
                "dimensions": profile["dimensions"],
                "revision": row.revision,
                "row_status": row.status,
            },
        )
        return identifier

    async def reconcile_intent(self, permit, value, run):
        from koinon.installation.intent_recovery import legacy_intent, pristine_descriptor
        from koinon.installation.writes import fingerprint

        workspace, provider_id, native, identifier, original = legacy_intent(permit, value, run)
        reader = self.reader.get()
        await reader.facade.catalog._lock_tenant(permit.tenant_id)
        row = await reader.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        provider = await reader.planner.provider(permit.tenant_id, provider_id, value.model_id)
        descriptor = pristine_descriptor(permit, value, run, row, provider, workspace, native, identifier)
        if await reader.records.find_initial_workspace_effects(
            permit.tenant_id, workspace, permit.run_id, identifier
        ):
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        if await reader.connections.selected(
            permit.tenant_id, workspace, value.domain, value.domain + ".embedding"
        ):
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        if await reader.adapter.workspace_exists(
            tenant_id=permit.tenant_id, workspace_id=workspace, domain=value.domain, actor=ACTOR
        ):
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        overview = await reader.adapter.overview(
            tenant_id=permit.tenant_id, workspace_id=workspace, domain=value.domain, actor=ACTOR
        )
        targets = await reader.adapter.discover(
            tenant_id=permit.tenant_id,
            native_workspace_id=workspace,
            catalog_workspace_id=workspace,
            domain=value.domain,
            actor=ACTOR,
            limit=1,
            offset=0,
        )
        if (
            overview["chunk_count"]
            or overview["active_native_id"] is not None
            or targets["total"]
            or targets["items"]
        ):
            raise InstallationError("INSTALLATION_MANUAL_CHANGE")
        receipt = {
            "status": "done",
            "resource_id": identifier,
            "dimensions": value.dimensions,
            "revision": 1,
            "row_status": "queued",
            "generation": permit.generation,
            "source_checkpoint_sha256": fingerprint(original),
            "descriptor_sha256": descriptor,
            "reason": "repository_defaults_26_11_1",
        }
        await reader.facade.catalog._audit(
            ACTOR,
            permit.tenant_id,
            "installation.index.intent_reconciled",
            identifier,
            {
                "run_id": permit.run_id,
                "generation": permit.generation,
                "source_checkpoint_sha256": receipt["source_checkpoint_sha256"],
                "descriptor_sha256": descriptor,
            },
        )
        await self.admissions.checkpoint(permit, "index-intent-reconciled:" + value.key, receipt)

    async def empty(self, reader, row):
        overview = await reader.adapter.overview(
            tenant_id=row.tenant_id, workspace_id=row.native_workspace_id, domain=row.domain, actor=ACTOR
        )
        if overview["chunk_count"] or overview["active_native_id"] not in {None, row.native_id}:
            raise InstallationError("INSTALLATION_INDEX_NOT_EMPTY")

    @transactional(read_from_primary=True)
    async def create(self, permit, value):
        run, reader, row, provider = await self.owned(permit, value)
        if "index-created:" + value.key in run.checkpoints:
            return
        workspace = await reader.facade.catalog.catalog_repository.find_by_id(row.workspace_id)
        binding = await reader.facade._workspace(
            ACTOR, permit.tenant_id, workspace, "canon" if row.domain == "documents" else "structured"
        )
        if binding.native_workspace_id != row.native_workspace_id:
            raise InstallationError("INSTALLATION_BINDING_CHANGED")
        await self.empty(reader, row)
        page = await reader.adapter.discover(
            tenant_id=row.tenant_id,
            native_workspace_id=row.native_workspace_id,
            catalog_workspace_id=row.workspace_id,
            domain=row.domain,
            actor=ACTOR,
            limit=2,
            offset=0,
        )
        if any(item["native_id"] != row.native_id for item in page["items"]):
            raise InstallationError("INSTALLATION_INDEX_EXISTS")
        native_fingerprint = await reader.adapter.create(row, actor=ACTOR, endpoint=provider.base_url)
        row.cursor = {"native_config_fingerprint": native_fingerprint}
        row.revision += 1
        await reader.records.save(row)
        await self.admissions.checkpoint(
            permit,
            "index-created:" + value.key,
            {
                "status": "done",
                "resource_id": row.id,
                "native_fingerprint": native_fingerprint,
                "revision": row.revision,
                "row_status": row.status,
            },
        )

    @transactional(read_from_primary=True)
    async def ready(self, permit, value):
        run, reader, row, _ = await self.owned(permit, value)
        if "index-ready:" + value.key in run.checkpoints:
            return
        NativeInstallationWrites.reference(run, "index-created", value.key)
        await self.empty(reader, row)
        with native_scope(
            "canon" if row.domain == "documents" else "structured",
            row.tenant_id,
            row.native_workspace_id,
            ACTOR,
        ):
            coverage = await reader.adapter.coverage(row)
            if coverage["chunk_count"] or coverage["vector_count"]:
                raise InstallationError("INSTALLATION_INDEX_NOT_EMPTY")
            if row.domain == "documents" and not await reader.adapter.provision_document(row):
                raise InstallationError("INSTALLATION_ANN_PROVISION_REQUIRED")
            await reader.adapter.set_state(row, "ready")
        actual = await reader.adapter.get_native(
            tenant_id=row.tenant_id,
            native_workspace_id=row.native_workspace_id,
            catalog_workspace_id=row.workspace_id,
            domain=row.domain,
            actor=ACTOR,
            identifier=row.id,
        )
        if actual is None or not actual["indexed"] or actual["chunk_count"] or actual["vector_count"]:
            raise InstallationError("INSTALLATION_ANN_UNQUALIFIED")
        row.status, row.indexed, row.qualification = "ready", True, actual["qualification"]
        row.revision += 1
        await reader.records.save(row)
        await self.admissions.checkpoint(
            permit,
            "index-ready:" + value.key,
            {
                "status": "done",
                "resource_id": row.id,
                "qualification": actual["qualification"],
                "revision": row.revision,
                "row_status": row.status,
            },
        )

    @transactional(read_from_primary=True)
    async def activate(self, permit, value):
        run, reader, row, _ = await self.owned(permit, value)
        previous = run.checkpoints.get("index-active:" + value.key)
        selected = await reader.connections.selected(
            permit.tenant_id, row.workspace_id, row.domain, row.domain + ".embedding"
        )
        if previous:
            if (
                selected is None
                or selected.id != previous["connection_id"]
                or selected.revision != previous["connection_revision"]
                or row.status != "active"
            ):
                raise InstallationError("INSTALLATION_MANUAL_CHANGE")
            return
        NativeInstallationWrites.reference(run, "index-ready", value.key)
        if selected is not None:
            raise InstallationError("INSTALLATION_CONNECTION_EXISTS")
        await self.empty(reader, row)
        await reader.adapter.activate(row, previous_native_id=None)
        actual = await reader.adapter.get_native(
            tenant_id=row.tenant_id,
            native_workspace_id=row.native_workspace_id,
            catalog_workspace_id=row.workspace_id,
            domain=row.domain,
            actor=ACTOR,
            identifier=row.id,
        )
        if (
            actual is None
            or not actual["active"]
            or not actual["indexed"]
            or actual["chunk_count"]
            or actual["vector_count"]
        ):
            raise InstallationError("INSTALLATION_INDEX_ACTIVATION_INCOMPLETE")
        connection = await reader.connections._write_connection(
            ACTOR,
            permit.tenant_id,
            ConnectionInput(
                workspace_id=row.workspace_id,
                domain=row.domain,
                role=row.domain + ".embedding",
                mode="provider",
                provider_id=row.provider_id,
                model_id=row.model_id,
                dimensions=row.dimensions,
                storage_dimensions=row.storage_dimensions,
                space_id=row.native_id,
            ),
        )
        row.status, row.active_slot, row.build_slot = "active", row.build_slot, None
        row.indexed, row.qualification = True, actual["qualification"]
        row.activated_at = await self.admissions.runs.clock()
        row.revision += 1
        await reader.records.save(row)
        await reader.facade.catalog._audit(
            ACTOR, permit.tenant_id, "installation.index.active", row.id, {"run_id": permit.run_id}
        )
        await self.admissions.checkpoint(
            permit,
            "index-active:" + value.key,
            {
                "status": "done",
                "resource_id": row.id,
                "connection_id": connection["id"],
                "connection_revision": connection["revision"],
                "revision": row.revision,
                "row_status": row.status,
            },
        )

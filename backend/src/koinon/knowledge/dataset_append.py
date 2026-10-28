# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Append file intake with a durable, exclusive canonical publication boundary."""

import json
from contextlib import suppress
from hashlib import sha256

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.errors import InvalidHierarchy
from koinon.knowledge.dataset_dtos import DatasetFileAppendResult, NativeDatasetFile
from koinon.knowledge.service import KnowledgeFacade


@service(name="knowledge.dataset_files")
class DatasetFiles:
    def __init__(self, knowledge: KnowledgeFacade):
        self.knowledge = knowledge

    async def scope(self, subject, tenant, dataset_id):
        chain = await self.knowledge._chain(subject, tenant, dataset_id, "ingest:write")
        dataset = chain[0]
        if dataset.kind != "dataset":
            raise InvalidHierarchy("Select a dataset", code="INVALID_DATASET")
        await self.knowledge.catalog.authorize(subject, tenant, "catalog:write", dataset.workspace_id)
        if self.knowledge.catalog.restriction:
            await self.knowledge.catalog.restriction.resource(subject, dataset, write=True)
        binding = await self.knowledge.binding(tenant, dataset_id, "structured", entry=dataset)
        aliases = await self.knowledge.bindings.find_all(
            tenant_id=tenant,
            domain="structured",
            entity_kind="dataset",
            native_id=binding.native_id,
            native_workspace_id=binding.native_workspace_id,
        )
        if {alias.catalog_id for alias in aliases} != {dataset_id}:
            raise ConflictException(
                "Appending requires one canonical dataset identity; reconcile aliases first",
                code="DATASET_APPEND_ALIAS_CONFLICT",
            )
        return dataset, binding

    @transactional
    async def claim(self, subject, tenant, dataset_id, filename, content, key_hash, payload_hash):
        await self.knowledge.catalog._scoped_entry(tenant, dataset_id, lock=True)
        dataset, binding = await self.scope(subject, tenant, dataset_id)
        existing = await self.knowledge.catalog.catalog_repository.file_intake_for_key(
            tenant, dataset_id, key_hash
        )
        if len(existing) > 1:
            raise ConflictException("Intake key has conflicting receipts", code="IDEMPOTENCY_CONFLICT")
        if existing:
            previous = existing[0]
            state = previous.metadata_json["_koinon_intake"]
            if state.get("payload_sha256") != payload_hash or previous.created_by != subject:
                raise ConflictException(
                    "This intake key belongs to another request", code="IDEMPOTENCY_CONFLICT"
                )
            if state.get("status") == "completed":
                return DatasetFileAppendResult.model_validate(state["receipt"])
            raise ConflictException("Reconcile the retained intake before retrying", code="DATASET_NOT_READY")
        if dataset.status != "ready":
            raise ConflictException(
                "Dataset intake is unfinished; reconcile the retained file version before retrying",
                code="DATASET_NOT_READY",
            )
        version = await self.knowledge.catalog.create(
            subject,
            tenant,
            kind="index_version",
            name=filename,
            parent_id=dataset_id,
            metadata={
                "operation": "dataset.append_file",
                "sha256": sha256(content).hexdigest(),
                "bytes": len(content),
                "previous_dataset_status": dataset.status,
            },
        )
        version = await self.knowledge.catalog.update(subject, tenant, version.id, {"status": "pending"})
        state = {
            "operation": "dataset.append_file",
            "version_id": version.id,
            "filename": filename,
            "sha256": sha256(content).hexdigest(),
            "byte_size": len(content),
            "key_sha256": key_hash,
            "payload_sha256": payload_hash,
            "status": "pending",
        }
        version.metadata_json = {**version.metadata_json, "_koinon_intake": dict(state)}
        await self.knowledge.catalog.catalog_repository.save(version)
        dataset = await self.knowledge.catalog.update(subject, tenant, dataset.id, {"status": "pending"})
        dataset.metadata_json = {
            **dataset.metadata_json,
            "_koinon_intake": dict(state),
        }
        await self.knowledge.catalog.catalog_repository.save(dataset)
        return binding, version

    @transactional
    async def publish(self, subject, tenant, dataset_id, version_id, expected_binding, result):
        await self.knowledge.catalog._scoped_entry(tenant, dataset_id, lock=True)
        dataset, binding = await self.scope(subject, tenant, dataset_id)
        if (
            dataset.status != "pending"
            or dataset.metadata_json.get("_koinon_intake", {}).get("version_id") != version_id
            or binding.native_id != expected_binding.native_id
            or binding.native_workspace_id != expected_binding.native_workspace_id
        ):
            raise ConflictException("Dataset intake changed", code="DATASET_APPEND_CONFLICT")
        version = await self.knowledge.catalog.get(subject, tenant, version_id)
        claim = dataset.metadata_json["_koinon_intake"]
        if (
            version.parent_id != dataset_id
            or version.status != "pending"
            or version.name != claim["filename"]
            or version.metadata_json.get("operation") != claim["operation"]
            or version.metadata_json.get("sha256") != claim["sha256"]
            or version.metadata_json.get("bytes") != claim["byte_size"]
        ):
            raise ConflictException("File intake changed", code="DATASET_APPEND_CONFLICT")
        for table in result.tables:
            existing = await self.knowledge.bindings.find_all(
                tenant_id=tenant,
                domain="structured",
                entity_kind="table",
                native_id=str(table.table_id),
                native_workspace_id=binding.native_workspace_id,
            )
            if existing:
                raise ConflictException("Appended table is already bound", code="DATASET_APPEND_CONFLICT")
        table_ids = []
        for table in result.tables:
            node = await self.knowledge.catalog.create(
                subject,
                tenant,
                kind="table",
                name=table.name,
                parent_id=dataset_id,
                metadata={"snapshot_id": str(table.snapshot_id), "file_version_id": version_id},
            )
            await self.knowledge._bind(
                subject,
                tenant,
                node,
                "structured",
                str(table.table_id),
                binding.native_workspace_id,
                {**table.model_dump(mode="json"), "file_id": str(result.file_id)},
            )
            table_ids.append(node.id)
        await self.knowledge._bind(
            subject,
            tenant,
            version,
            "structured",
            str(result.file_id),
            binding.native_workspace_id,
            {"dataset_id": binding.native_id, "table_ids": table_ids},
        )
        receipt = DatasetFileAppendResult(
            dataset_id=dataset_id,
            file_version_id=version.id,
            filename=claim["filename"],
            sha256=claim["sha256"],
            byte_size=claim["byte_size"],
            table_ids=table_ids,
        )
        version = await self.knowledge.catalog.update(subject, tenant, version.id, {"status": "ready"})
        version.metadata_json = {
            **version.metadata_json,
            "_koinon_intake": {**claim, "status": "completed", "receipt": receipt.model_dump(mode="json")},
        }
        await self.knowledge.catalog.catalog_repository.save(version)
        dataset = await self.knowledge.catalog.update(subject, tenant, dataset_id, {"status": "ready"})
        dataset.metadata_json = {
            key: value for key, value in dataset.metadata_json.items() if key != "_koinon_intake"
        }
        await self.knowledge.catalog.catalog_repository.save(dataset)
        return receipt

    @transactional
    async def failed(self, subject, tenant, dataset_id, version_id, error):
        dataset = await self.knowledge.catalog._scoped_entry(tenant, dataset_id, lock=True)
        if (
            dataset.metadata_json.get("_koinon_intake", {}).get("version_id") != version_id
            or dataset.status != "pending"
        ):
            return
        version = await self.knowledge.catalog.get(subject, tenant, version_id)
        await self.knowledge.catalog.update(
            subject,
            tenant,
            version_id,
            {
                "status": "error",
                "metadata": {
                    **{key: value for key, value in version.metadata_json.items() if key != "_koinon_intake"},
                    "failure_type": type(error).__name__,
                    "reconciliation_required": True,
                },
            },
        )
        await self.knowledge.catalog.update(subject, tenant, dataset_id, {"status": "error"})

    async def append(self, subject, tenant, dataset_id, *, filename, content, idempotency_key):
        if not isinstance(filename, str) or filename != filename.strip():
            raise InvalidRequestException(
                "Use a filename without surrounding whitespace", code="INVALID_UPLOAD"
            )
        if (
            not isinstance(idempotency_key, str)
            or not idempotency_key.strip()
            or len(idempotency_key) > 255
            or any(ord(character) < 32 or ord(character) == 127 for character in idempotency_key)
        ):
            raise InvalidRequestException(
                "Supply an Idempotency-Key up to255 characters", code="INVALID_IDEMPOTENCY_KEY"
            )
        self.knowledge._validate_file(filename, content)
        payload_hash = sha256(
            json.dumps(
                [dataset_id, filename, sha256(content).hexdigest(), len(content)], separators=(",", ":")
            ).encode()
        ).hexdigest()
        claimed = await self.claim(
            subject,
            tenant,
            dataset_id,
            filename,
            content,
            sha256(idempotency_key.encode()).hexdigest(),
            payload_hash,
        )
        if isinstance(claimed, DatasetFileAppendResult):
            return claimed
        binding, version = claimed
        try:
            result = NativeDatasetFile.model_validate(
                await self.knowledge.domains.append_dataset_file(
                    tenant_id=tenant,
                    workspace_id=binding.native_workspace_id,
                    catalog_workspace_id=binding.workspace_id,
                    dataset_id=binding.native_id,
                    filename=filename,
                    content=content,
                    actor=subject,
                    source_catalog_id=dataset_id,
                )
            )
            return await self.publish(subject, tenant, dataset_id, version.id, binding, result)
        except BaseException as error:
            # Native sections commit independently. A failed or revoked operation must remain closed.
            with suppress(Exception):
                await self.failed(subject, tenant, dataset_id, version.id, error)
            raise

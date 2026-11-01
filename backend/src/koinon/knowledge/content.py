# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Content updates preserve native identity and record actual revision effects."""

import re
from hashlib import sha256

from pydantic import JsonValue
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.mappers import entry_dto
from koinon.knowledge.availability.repository import ATTEMPT_KEY, mark_content_attempt
from koinon.knowledge.dtos import DocumentRevisionPreconditions
from koinon.knowledge.service import KnowledgeFacade


@service(name="knowledge.content_updates")
class ContentUpdates:
    def __init__(self, knowledge: KnowledgeFacade):
        self.knowledge = knowledge

    async def reingest_document(
        self,
        subject,
        tenant,
        document_id,
        *,
        expected_sha256,
        acknowledge_chunk_invalidation=False,
        expected_source_version_id=None,
        expected_extraction_id=None,
    ):
        _, binding, _ = await self._document_scope(subject, tenant, document_id)
        self._document_precondition(expected_sha256, acknowledge_chunk_invalidation)
        await self._document_revision_precondition(
            subject, tenant, binding, expected_source_version_id, expected_extraction_id
        )
        original = await self.knowledge.domains.document_original(
            tenant_id=tenant,
            workspace_id=binding.native_workspace_id,
            source_id=binding.native_id,
            actor=subject,
            max_bytes=self.knowledge.settings.max_upload_bytes,
        )
        return await self.document(
            subject,
            tenant,
            document_id,
            filename=original["filename"],
            content=original["content"],
            expected_sha256=expected_sha256,
            acknowledge_chunk_invalidation=True,
            force_reingest=True,
            expected_source_version_id=expected_source_version_id,
            expected_extraction_id=expected_extraction_id,
        )

    async def reingest_table(self, subject, tenant, dataset_id, table_id, *, expected_snapshot_id):
        _, table, dataset, _ = await self._table_scope(subject, tenant, dataset_id, table_id)
        if not expected_snapshot_id or len(expected_snapshot_id) > 64:
            raise InvalidRequestException(
                "Supply the current table snapshot in If-Match", code="CONTENT_VERSION_REQUIRED"
            )
        original = await self.knowledge.domains.table_original(
            tenant_id=tenant,
            workspace_id=table.native_workspace_id,
            dataset_id=dataset.native_id,
            table_id=table.native_id,
            expected_snapshot_id=expected_snapshot_id,
            actor=subject,
            max_bytes=self.knowledge.settings.max_upload_bytes,
        )
        return await self.table(
            subject,
            tenant,
            dataset_id,
            table_id,
            filename=original["filename"],
            content=original["content"],
            expected_snapshot_id=expected_snapshot_id,
            reingested_from_file_id=original["file_id"],
        )

    async def _writable(self, subject, tenant, identifier):
        chain = await self.knowledge._chain(subject, tenant, identifier, "ingest:write")
        if chain[0].kind == "dataset" and chain[0].metadata_json.get("_koinon_intake"):
            raise ConflictException(
                "Reconcile the retained dataset file intake before replacing a table",
                code="DATASET_NOT_READY",
            )
        await self.knowledge.catalog.authorize(subject, tenant, "catalog:write", chain[-1].id)
        if self.knowledge.catalog.restriction:
            await self.knowledge.catalog.restriction.resource(subject, chain[0], write=True)
        return chain

    @transactional(datasource="primary")
    async def _version(self, subject, tenant, parent, operation, filename, content):
        version = await self.knowledge.catalog.create(
            subject,
            tenant,
            kind="index_version",
            name=filename,
            parent_id=parent,
            metadata={"operation": operation, "sha256": sha256(content).hexdigest(), "bytes": len(content)},
        )
        version = await self.knowledge.catalog.update(subject, tenant, version.id, {"status": "pending"})
        await mark_content_attempt(self.knowledge.catalog.catalog_repository, version, operation)
        await self.knowledge.catalog._audit(
            subject,
            tenant,
            "knowledge.content.recorded",
            version.id,
            {"operation": operation, "state": "unknown"},
        )
        return version

    @transactional(datasource="primary")
    async def _finish_version(self, subject, tenant, version, fields, state):
        version = await self.knowledge.catalog.update(subject, tenant, version.id, fields)
        marker = version.metadata_json[ATTEMPT_KEY]
        await mark_content_attempt(
            self.knowledge.catalog.catalog_repository, version, marker["operation"], state
        )
        await self.knowledge.catalog._audit(
            subject,
            tenant,
            "knowledge.content.recorded",
            version.id,
            {"operation": marker["operation"], "state": state},
        )
        return version

    @transactional
    async def _claim_tables(self, subject, tenant, entries):
        catalog = self.knowledge.catalog
        for entry in sorted((entry for entry in entries if entry.kind == "dataset"), key=lambda row: row.id):
            current = await catalog._scoped_entry(tenant, entry.id, lock=True)
            await self._writable(subject, tenant, current.id)
            if current.status == "pending":
                raise ConflictException("Dataset content is being updated", code="DATASET_NOT_READY")
        for entry in entries:
            await catalog.update(subject, tenant, entry.id, {"status": "pending"})

    async def _run(self, subject, tenant, entries, version, operation, *, preserve_previous=False):
        catalog = self.knowledge.catalog
        previous = {entry.id: entry.status for entry in entries}
        claimed = any(entry.kind == "dataset" for entry in entries)
        if claimed:
            await self._claim_tables(subject, tenant, entries)
        try:
            if not claimed:
                for entry in entries:
                    await catalog.update(subject, tenant, entry.id, {"status": "pending"})
            effects = await operation()
            for entry in entries:
                current = await catalog.get(subject, tenant, entry.id)
                metadata = {
                    key: value for key, value in current.metadata_json.items() if key != "_koinon_lifecycle"
                }
                await catalog.update(
                    subject,
                    tenant,
                    entry.id,
                    {
                        "status": "ready",
                        "metadata": {**metadata, "latest_content_version_id": version.id},
                    },
                )
            version = await self._finish_version(
                subject,
                tenant,
                version,
                {
                    "status": "ready",
                    "metadata": {
                        **{key: value for key, value in version.metadata_json.items() if key != ATTEMPT_KEY},
                        "effects": effects,
                    },
                },
                "complete",
            )
            return version, effects
        except Exception as error:
            for entry in entries:
                await catalog.update(
                    subject,
                    tenant,
                    entry.id,
                    {
                        "status": previous[entry.id]
                        if preserve_previous or isinstance(error, ConflictException)
                        else "error",
                    },
                )
            await self._finish_version(
                subject,
                tenant,
                version,
                {
                    "status": "error",
                    "metadata": {
                        **{key: value for key, value in version.metadata_json.items() if key != ATTEMPT_KEY},
                        "failure_type": type(error).__name__,
                        "failure_code": getattr(error, "code", None),
                    },
                },
                "failed",
            )
            raise

    def _document_precondition(self, expected_sha256, acknowledge_chunk_invalidation):
        if not isinstance(expected_sha256, str) or re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256) is None:
            raise InvalidRequestException(
                "Supply the current original SHA256 in If-Match", code="CONTENT_VERSION_REQUIRED"
            )
        if acknowledge_chunk_invalidation is not True:
            raise InvalidRequestException(
                "Acknowledge that replacement invalidates previous chunk IDs",
                code="CHUNK_INVALIDATION_ACK_REQUIRED",
            )

    async def _document_scope(self, subject, tenant, document_id):
        chain = await self._writable(subject, tenant, document_id)
        if chain[0].kind != "document":
            raise InvalidHierarchy("Select a document", code="INVALID_DOCUMENT")
        binding = await self.knowledge.binding(tenant, document_id, "canon", entry=chain[0])
        aliases = await self.knowledge.bindings.find_all(
            tenant_id=tenant,
            domain="canon",
            native_id=binding.native_id,
            native_workspace_id=binding.native_workspace_id,
        )
        entries = {}
        for alias in aliases:
            if alias.entity_kind not in {"source", "document"}:
                continue
            entry = (await self._writable(subject, tenant, alias.catalog_id))[0]
            await self.knowledge.binding(tenant, entry.id, "canon", entry=entry)
            if entry.workspace_id != chain[0].workspace_id:
                raise AccessDenied("A content alias has incompatible scope", code="BINDING_SCOPE_MISMATCH")
            entries[entry.id] = entry
        if set(entries) != {chain[0].id, chain[1].id}:
            raise ConflictException(
                "Review the source’s affected catalog items before changing its content",
                code="DOCUMENT_ALIASED_CHANGE_REVIEW_REQUIRED",
            )
        return chain, binding, entries

    async def _document_revision_precondition(self, subject, tenant, binding, version, extraction):
        expected = DocumentRevisionPreconditions(
            expected_source_version_id=version, expected_extraction_id=extraction
        )
        pair = expected.model_dump(mode="json")
        observed = await self.knowledge.domains.document_revision(
            tenant_id=tenant,
            workspace_id=binding.native_workspace_id,
            source_id=binding.native_id,
            actor=subject,
        )
        wanted = (pair["expected_source_version_id"], pair["expected_extraction_id"])
        actual = (observed["source_version_id"], observed["extraction_id"]) if observed else (None, None)
        if actual != wanted:
            raise ConflictException(
                "Document version or extraction changed; review its current content",
                code="DOCUMENT_VERSION_CONFLICT" if all(wanted) else "DOCUMENT_VERSION_REQUIRED",
            )

    async def document(
        self,
        subject,
        tenant,
        document_id,
        *,
        filename,
        content,
        expected_sha256,
        acknowledge_chunk_invalidation=False,
        force_reingest=False,
        _on_version=None,
        expected_source_version_id=None,
        expected_extraction_id=None,
    ):
        chain, binding, entries = await self._document_scope(subject, tenant, document_id)
        self.knowledge._validate_file(filename, content)
        self._document_precondition(expected_sha256, acknowledge_chunk_invalidation)
        await self._document_revision_precondition(
            subject, tenant, binding, expected_source_version_id, expected_extraction_id
        )
        version = await self._version(
            subject,
            tenant,
            chain[1].id,
            "document.reingest" if force_reingest else "document.replace",
            filename,
            content,
        )
        if _on_version is not None:
            await _on_version(version)

        async def replace() -> dict[str, JsonValue]:
            async def authorize_commit():
                _, current_binding, current_entries = await self._document_scope(subject, tenant, document_id)
                if current_binding.native_id != binding.native_id or set(current_entries) != set(entries):
                    raise ConflictException(
                        "Affected documents changed; review the operation again",
                        code="DOCUMENT_AFFECTED_SET_CHANGED",
                    )

            result = await self.knowledge.domains.replace_document(
                tenant_id=tenant,
                workspace_id=binding.native_workspace_id,
                catalog_workspace_id=chain[0].workspace_id,
                source_id=binding.native_id,
                filename=filename,
                content=content,
                expected_sha256=expected_sha256.lower(),
                actor=subject,
                force_reingest=force_reingest,
                logical_source_key=chain[1].id,
                operation_id=version.id,
                authorize_commit=authorize_commit,
                expected_source_version_id=expected_source_version_id,
                expected_extraction_id=expected_extraction_id,
            )
            for entry in entries.values():
                metadata = {
                    key: value for key, value in entry.metadata_json.items() if key != "_koinon_lifecycle"
                }
                await self.knowledge.catalog.update(
                    subject,
                    tenant,
                    entry.id,
                    {
                        "metadata": {
                            **metadata,
                            "sha256": sha256(content).hexdigest(),
                            "bytes": len(content),
                        },
                    },
                )
            return {
                **result,
                "citation_rows_preserved": True,
                "previous_chunk_ids_invalidated": not result.get("unchanged", False),
                "affected_asset_ids": [entry.id for entry in entries.values() if entry.kind == "document"],
            }

        version, effects = await self._run(
            subject, tenant, list(entries.values()), version, replace, preserve_previous=True
        )
        await self.knowledge._bind(
            subject, tenant, version, "canon", binding.native_id, binding.native_workspace_id, effects
        )
        return {
            "asset": entry_dto(await self.knowledge.catalog.get(subject, tenant, document_id)),
            "source": entry_dto(await self.knowledge.catalog.get(subject, tenant, chain[1].id)),
            "version": entry_dto(version),
            "effects": effects,
        }

    async def _table_scope(self, subject, tenant, dataset_id, table_id):
        chain = await self._writable(subject, tenant, table_id)
        if chain[0].kind != "table" or chain[1].id != dataset_id or chain[1].kind != "dataset":
            raise InvalidHierarchy("Select a table belonging to this dataset", code="INVALID_TABLE_PARENT")
        dataset = (await self._writable(subject, tenant, dataset_id))[0]
        table_binding = await self.knowledge.binding(tenant, table_id, "structured", entry=chain[0])
        dataset_binding = await self.knowledge.binding(tenant, dataset_id, "structured", entry=dataset)
        entries = {dataset.id: dataset, chain[0].id: chain[0]}
        for native_id, kind in ((table_binding.native_id, "table"), (dataset_binding.native_id, "dataset")):
            aliases = await self.knowledge.bindings.find_all(
                tenant_id=tenant,
                domain="structured",
                native_id=native_id,
                native_workspace_id=table_binding.native_workspace_id,
            )
            for alias in aliases:
                if alias.entity_kind != kind:
                    continue
                alias_chain = await self._writable(subject, tenant, alias.catalog_id)
                admitted = await self.knowledge.binding(
                    tenant, alias.catalog_id, "structured", entry=alias_chain[0]
                )
                if admitted.workspace_id != table_binding.workspace_id:
                    raise AccessDenied(
                        "A content alias has incompatible scope", code="BINDING_SCOPE_MISMATCH"
                    )
                entries[alias_chain[0].id] = alias_chain[0]
                if kind == "table":
                    parent = (await self._writable(subject, tenant, alias_chain[1].id))[0]
                    parent_binding = await self.knowledge.binding(
                        tenant, parent.id, "structured", entry=parent
                    )
                    if parent_binding.native_id != dataset_binding.native_id:
                        raise AccessDenied(
                            "A table alias has an incompatible dataset", code="BINDING_SCOPE_MISMATCH"
                        )
                    entries[parent.id] = parent
        return chain, table_binding, dataset_binding, entries

    async def table(
        self,
        subject,
        tenant,
        dataset_id,
        table_id,
        *,
        filename,
        content,
        expected_snapshot_id,
        reingested_from_file_id=None,
        _on_version=None,
    ):
        chain, table_binding, dataset_binding, entries = await self._table_scope(
            subject, tenant, dataset_id, table_id
        )
        self.knowledge._validate_file(filename, content)
        if not expected_snapshot_id or len(expected_snapshot_id) > 64:
            raise InvalidRequestException(
                "Supply the current table snapshot in If-Match", code="CONTENT_VERSION_REQUIRED"
            )
        version = await self._version(
            subject,
            tenant,
            dataset_id,
            "table.reingest" if reingested_from_file_id is not None else "table.reupload",
            filename,
            content,
        )
        if _on_version is not None:
            await _on_version(version)

        async def reupload():
            result = await self.knowledge.domains.reupload_table(
                tenant_id=tenant,
                workspace_id=table_binding.native_workspace_id,
                catalog_workspace_id=chain[0].workspace_id,
                dataset_id=dataset_binding.native_id,
                table_id=table_binding.native_id,
                filename=filename,
                content=content,
                expected_snapshot_id=expected_snapshot_id,
                actor=subject,
                operation="reingest" if reingested_from_file_id is not None else "replace",
            )
            for entry in entries.values():
                if entry.kind == "table":
                    current = await self.knowledge.catalog.get(subject, tenant, entry.id)
                    await self.knowledge.catalog.update(
                        subject,
                        tenant,
                        entry.id,
                        {"metadata": {**current.metadata_json, "snapshot_id": result["snapshot_id"]}},
                    )
            return {
                **result,
                "historical_snapshots_preserved": True,
                "table_id": table_id,
                "affected_asset_ids": list(entries),
                **(
                    {"reingested_from_file_id": reingested_from_file_id}
                    if reingested_from_file_id is not None
                    else {}
                ),
            }

        version, effects = await self._run(subject, tenant, list(entries.values()), version, reupload)
        await self.knowledge._bind(
            subject,
            tenant,
            version,
            "structured",
            effects["file_id"],
            table_binding.native_workspace_id,
            effects,
        )
        return {
            "asset": entry_dto(await self.knowledge.catalog.get(subject, tenant, dataset_id)),
            "table": entry_dto(await self.knowledge.catalog.get(subject, tenant, table_id)),
            "version": entry_dto(version),
            "effects": effects,
        }

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from pyfly.container import Provider, component, service
from pyfly.core import config_properties
from pyfly.kernel import (
    ConflictException,
    DuplicateKeyException,
    InvalidRequestException,
    PayloadTooLargeException,
)

from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.mappers import entry_dto
from koinon.catalog.service import PARENTS, CatalogService
from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.curated.ports import CuratedCorpusPort
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.organization_knowledge.runtime import settings_for_operation
from koinon.organization_knowledge.service import OrganizationKnowledgeService


@component(name="knowledge.settings")
@config_properties(prefix="koinon.knowledge")
@dataclass
class KnowledgeSettings:
    max_upload_bytes: int = 32 * 1024 * 1024
    max_search_workspaces: int = 32
    max_lineage_nodes: int = 1000


@service(name="knowledge.facade")
class KnowledgeFacade:
    def __init__(
        self,
        catalog: CatalogService,
        bindings: DomainBindingRepository,
        domains: NativeDomains,
        settings: KnowledgeSettings,
        curated: Provider[CuratedCorpusPort | None] | None = None,
        knowledge_settings: OrganizationKnowledgeService | None = None,
    ):
        self.catalog, self.bindings, self.domains, self.settings = catalog, bindings, domains, settings
        self.curated = curated
        self.knowledge_settings = knowledge_settings

    async def _chain(self, subject: str, tenant_id: str, entry_id: str, permission="catalog:read"):
        chain, seen = [], set()
        current = entry_id
        while current is not None:
            if current in seen or len(seen) >= 16:
                raise InvalidHierarchy("Catalog ancestry is cyclic or too deep", code="INVALID_ANCESTRY")
            seen.add(current)
            entry = await self.catalog.get(subject, tenant_id, current)
            if entry.status == "archived":
                raise AccessDenied("This resource or its ancestor is archived", code="RESOURCE_ARCHIVED")
            chain.append(entry)
            current = entry.parent_id
        if not chain or chain[-1].kind != "workspace":
            raise InvalidHierarchy("Resource has no valid workspace ancestor", code="INVALID_ANCESTRY")
        workspace = chain[-1]
        project = next((entry for entry in chain if entry.kind == "project"), None)
        for index, entry in enumerate(chain):
            parent = chain[index + 1] if index + 1 < len(chain) else None
            if (parent.kind if parent else None) not in PARENTS.get(entry.kind, ()):
                raise InvalidHierarchy("Resource ancestry has incompatible kinds", code="INVALID_ANCESTRY")
            if entry.workspace_id != workspace.id or (
                entry.kind != "workspace" and entry.project_id != (project.id if project else None)
            ):
                raise InvalidHierarchy("Resource ancestry disagrees with its scope", code="INVALID_ANCESTRY")
        await self.catalog.authorize(subject, tenant_id, permission, workspace.id)
        return chain

    async def binding(self, tenant_id: str, catalog_id: str, domain: str, *, entry=None) -> DomainBinding:
        rows = await self.bindings.find_all(tenant_id=tenant_id, catalog_id=catalog_id, domain=domain)
        if not rows:
            raise AccessDenied("The resource has no admitted domain binding", code="BINDING_UNAVAILABLE")
        binding = rows[0]
        if entry is not None and (
            binding.workspace_id != entry.workspace_id or binding.entity_kind != entry.kind
        ):
            raise AccessDenied("Native binding scope disagrees with catalog", code="BINDING_SCOPE_MISMATCH")
        if entry is not None:
            workspace = (
                binding
                if entry.kind == "workspace"
                else await self.binding(tenant_id, entry.workspace_id, domain)
            )
            if binding.native_workspace_id != workspace.native_id or workspace.entity_kind != "workspace":
                raise AccessDenied(
                    "Native workspace disagrees with its admitted workspace binding",
                    code="BINDING_SCOPE_MISMATCH",
                )
        return binding

    async def _bind(self, subject, tenant_id, entry, domain, native_id, native_workspace_id, details=None):
        rows = await self.bindings.find_all(tenant_id=tenant_id, catalog_id=entry.id, domain=domain)
        if rows:
            if rows[0].native_id != str(native_id) or rows[0].native_workspace_id != str(native_workspace_id):
                raise InvalidHierarchy(
                    "An existing native binding cannot be replaced", code="BINDING_CONFLICT"
                )
            return rows[0]
        binding = DomainBinding(
            id=str(uuid4()),
            tenant_id=tenant_id,
            catalog_id=entry.id,
            workspace_id=entry.workspace_id,
            domain=domain,
            entity_kind=entry.kind,
            native_id=str(native_id),
            native_workspace_id=str(native_workspace_id),
            details_json=details or {},
            created_by=subject,
        )
        try:
            return await self.bindings.save(binding)
        except DuplicateKeyException:
            existing = await self.binding(tenant_id, entry.id, domain)
            if existing.native_id != str(native_id):
                raise InvalidHierarchy(
                    "Concurrent native bindings disagree", code="BINDING_CONFLICT"
                ) from None
            return existing

    async def _workspace(self, subject, tenant_id, workspace, domain):
        rows = await self.bindings.find_all(tenant_id=tenant_id, catalog_id=workspace.id, domain=domain)
        if rows:
            return await self.binding(tenant_id, workspace.id, domain, entry=workspace)
        native = await self.domains.ensure_workspace(
            domain=domain, tenant_id=tenant_id, catalog_id=workspace.id, name=workspace.name, actor=subject
        )
        return await self._bind(subject, tenant_id, workspace, domain, native, native)

    async def upload(
        self,
        subject,
        tenant_id,
        *,
        workspace_id,
        project_id,
        parent_id,
        mode,
        filename,
        content: bytes,
        _on_source=None,
    ):
        chain = await self._chain(subject, tenant_id, parent_id, "ingest:write")
        parent, workspace = chain[0], chain[-1]
        if (
            parent.kind not in {"collection", "corpus"}
            or workspace.id != workspace_id
            or parent.project_id != project_id
        ):
            raise InvalidHierarchy(
                "Select matching workspace, project and collection/corpus", code="INVALID_PARENT"
            )
        self._validate_file(filename, content)
        if mode not in {"document", "dataset"}:
            raise InvalidRequestException("Choose document or dataset mode", code="INVALID_INGEST_MODE")
        metadata = {"sha256": sha256(content).hexdigest(), "bytes": len(content), "mode": mode}
        source = await self.catalog.create(
            subject, tenant_id, kind="source", name=filename, parent_id=parent_id, metadata=metadata
        )
        await self.catalog.update(subject, tenant_id, source.id, {"status": "pending"})
        if _on_source is not None:
            await _on_source(await self.catalog.get(subject, tenant_id, source.id))
        domain = "canon" if mode == "document" else "structured"
        created_assets = []
        try:
            native_workspace = await self._workspace(subject, tenant_id, workspace, domain)
            arguments = dict(
                tenant_id=tenant_id,
                workspace_id=native_workspace.native_id,
                catalog_workspace_id=workspace.id,
                filename=filename,
                content=content,
                actor=subject,
                source_catalog_id=source.id,
            )
            if mode == "document":

                async def authorize_document_commit():
                    await self._chain(subject, tenant_id, source.id, "ingest:write")
                    await self.catalog.authorize(subject, tenant_id, "catalog:write", workspace.id)

                arguments["authorize_commit"] = authorize_document_commit
            result = await (
                self.domains.ingest_document(**arguments)
                if mode == "document"
                else self.domains.ingest_dataset(**arguments)
            )
            native_id = result["source_id"] if mode == "document" else result["file_id"]
            await self._bind(
                subject, tenant_id, source, domain, native_id, native_workspace.native_id, result
            )
            asset = await self.catalog.create(
                subject,
                tenant_id,
                kind=mode,
                name=filename,
                parent_id=source.id,
                metadata={"sha256": metadata["sha256"]},
            )
            created_assets.append(asset)
            await self.catalog.update(subject, tenant_id, asset.id, {"status": "pending"})
            await self._bind(
                subject,
                tenant_id,
                asset,
                domain,
                result["source_id"] if mode == "document" else result["dataset_id"],
                native_workspace.native_id,
                result,
            )
            for table in result.get("tables", []):
                node = await self.catalog.create(
                    subject,
                    tenant_id,
                    kind="table",
                    name=table["name"],
                    parent_id=asset.id,
                    metadata={"snapshot_id": table.get("snapshot_id")},
                )
                created_assets.append(node)
                await self.catalog.update(subject, tenant_id, node.id, {"status": "pending"})
                await self._bind(
                    subject, tenant_id, node, domain, table["table_id"], native_workspace.native_id, table
                )
            for created in created_assets:
                await self.catalog.update(subject, tenant_id, created.id, {"status": "ready"})
            asset = await self.catalog.get(subject, tenant_id, asset.id)
            source = await self.catalog.update(subject, tenant_id, source.id, {"status": "ready"})
            return {"source": entry_dto(source), "assets": [entry_dto(asset)]}
        except Exception as error:
            for created in created_assets:
                await self.catalog.update(subject, tenant_id, created.id, {"status": "error"})
            await self.catalog.update(
                subject,
                tenant_id,
                source.id,
                {"status": "error", "metadata": {**metadata, "failure_type": type(error).__name__}},
            )
            raise

    def _validate_file(self, filename, content):
        if (
            not filename
            or len(filename) > 255
            or filename in {".", ".."}
            or any(character in filename for character in ("/", "\\", "\0"))
        ):
            raise ValueError("Use a filename without directory components")
        if not content:
            raise InvalidRequestException("The uploaded file is empty", code="EMPTY_UPLOAD")
        if len(content) > self.settings.max_upload_bytes:
            raise PayloadTooLargeException(
                "Upload exceeds the configured byte limit", code="UPLOAD_TOO_LARGE"
            )

    async def search(
        self,
        subject,
        tenant_id,
        *,
        question,
        workspace_id=None,
        project_id=None,
        collection_id=None,
        asset_ids=None,
        limit=10,
        answer=False,
        _capture: NativeEvidenceReceipt | None = None,
    ):
        if not question.strip() or not 1 <= limit <= 100:
            raise InvalidRequestException(
                "Supply a question and a limit from 1 to 100", code="INVALID_SEARCH"
            )
        for identifier, kinds in (
            (workspace_id, {"workspace"}),
            (project_id, {"project"}),
            (collection_id, {"collection", "corpus"}),
        ):
            if identifier:
                selected = (await self._chain(subject, tenant_id, identifier, "knowledge:search"))[0]
                if selected.kind not in kinds or (workspace_id and selected.workspace_id != workspace_id):
                    raise InvalidHierarchy(
                        "Search filters disagree with their ancestry", code="INVALID_SEARCH_SCOPE"
                    )
                if project_id and selected.kind not in {"workspace"} and selected.project_id != project_id:
                    raise InvalidHierarchy(
                        "Search filters disagree with their project", code="INVALID_SEARCH_SCOPE"
                    )
        if asset_ids is not None and (
            not isinstance(asset_ids, list)
            or len(asset_ids) > 128
            or any(
                not isinstance(identifier, str) or not 1 <= len(identifier) <= 64 for identifier in asset_ids
            )
        ):
            raise InvalidRequestException("Select at most 128 valid asset IDs", code="INVALID_ASSET_SCOPE")
        assets = (
            await self.catalog.list(subject, tenant_id, kind="document", workspace_id=workspace_id)
            if asset_ids is None
            else [
                (await self._chain(subject, tenant_id, identifier, "knowledge:search"))[0]
                for identifier in dict.fromkeys(asset_ids)
            ]
        )
        curated = self.curated.get() if self.curated is not None else None
        if asset_ids is None and curated is not None:
            assets += await self.catalog.list(
                subject, tenant_id, kind="knowledge_item", workspace_id=workspace_id
            )
        groups = {}
        curated_groups = {}
        for asset in assets:
            chain = await self._chain(subject, tenant_id, asset.id, "knowledge:search")
            mismatched = (
                asset.kind not in {"document", "knowledge_item"}
                or (workspace_id and asset.workspace_id != workspace_id)
                or (project_id and asset.project_id != project_id)
                or (collection_id and collection_id not in {entry.id for entry in chain})
            )
            if mismatched:
                if asset_ids is not None:
                    raise InvalidHierarchy(
                        "Selected assets disagree with the document search context",
                        code="INVALID_ASSET_SCOPE",
                    )
                continue
            binding = await self.binding(tenant_id, asset.id, "canon", entry=asset)
            if asset.kind == "knowledge_item":
                if curated is None:
                    raise AccessDenied("Curated retrieval is unavailable", code="KNOWLEDGE_UNAVAILABLE")
                key = (asset.workspace_id, binding.native_workspace_id)
                groups.setdefault(key, {})
                curated_groups.setdefault(key, {})[binding.native_id] = (asset, chain[1])
                continue
            groups.setdefault((asset.workspace_id, binding.native_workspace_id), {})[binding.native_id] = (
                asset,
                chain[1],
            )
        if len(groups) > self.settings.max_search_workspaces:
            raise InvalidRequestException(
                "Narrow the search to a workspace or project", code="SEARCH_SCOPE_TOO_WIDE"
            )
        hits, citations, answers = [], [], []
        policy = await settings_for_operation(self.knowledge_settings, subject, tenant_id)
        _capture = _capture or NativeEvidenceReceipt(subject, tenant_id)
        for (catalog_workspace, native_workspace), admitted in groups.items():
            knowledge = curated_groups.get((catalog_workspace, native_workspace), {})
            admitted_ids = tuple(asset.id for asset, _ in [*admitted.values(), *knowledge.values()])

            async def authorize_model(asset_ids=admitted_ids):
                for admitted_id in asset_ids:
                    await self._chain(subject, tenant_id, admitted_id, "knowledge:search")

            _capture.authorize_model = authorize_model
            if _capture is not None:
                _capture.admit_documents(tenant_id, native_workspace, subject, admitted)
            curated_retrieve = None
            if knowledge and curated is not None:
                selections = await curated.admit(
                    subject, tenant_id, [asset.id for asset, _ in knowledge.values()]
                )

                async def fetch_curated(*, query, limit, selected=selections, native=native_workspace):
                    return await curated.search(
                        subject, tenant_id, native, selected, query=query, limit=limit, _capture=_capture
                    )

                curated_retrieve = fetch_curated
            result = await self.domains.search(
                tenant_id=tenant_id,
                workspace_id=native_workspace,
                catalog_workspace_id=catalog_workspace,
                source_ids=sorted(admitted),
                question=question,
                limit=limit,
                answer=answer,
                actor=subject,
                _knowledge_settings_snapshot=policy,
                **({"_capture": _capture} if _capture is not None else {}),
                **({"_curated_retrieve": curated_retrieve} if curated_retrieve is not None else {}),
            )
            for hit in result.get("hits", []):
                source_id = hit.get("source_id")
                if hit.get("source_kind") == "knowledge_version":
                    if source_id not in knowledge:
                        raise AccessDenied(
                            "Domain returned unadmitted knowledge", code="DOMAIN_SCOPE_MISMATCH"
                        )
                    asset, _ = knowledge[source_id]
                    proof = _capture.knowledge_sources.get(str(hit.get("chunk_id")))
                    if proof is None or proof.asset_id != asset.id:
                        raise AccessDenied(
                            "Exact committed knowledge provenance is required", code="EVIDENCE_UNAVAILABLE"
                        )
                    hits.append(
                        {
                            "id": str(hit["chunk_id"]),
                            "title": proof.title,
                            "text": hit.get("content", ""),
                            "score": hit.get("score", 0),
                            "asset_id": asset.id,
                            "source_id": None,
                            "kind": "knowledge_version",
                            "knowledge_item_id": asset.id,
                            "knowledge_version_id": proof.knowledge_version_id,
                            "knowledge_version": proof.knowledge_version,
                        }
                    )
                    continue
                if source_id not in admitted:
                    raise AccessDenied("Domain returned an unadmitted source", code="DOMAIN_SCOPE_MISMATCH")
                asset, source = admitted[source_id]
                identifier = str(hit.get("chunk_id") or hit.get("id"))
                observed = _capture.documents.get(identifier)
                source_reference = None
                if observed is not None:
                    content = hit.get("content")
                    if (
                        observed.workspace_id != native_workspace or observed.source_id != source_id
                        or observed.chunk_id != identifier or not isinstance(content, str)
                        or observed.digest != sha256(content.encode()).hexdigest()
                        or observed.quote != content[:8000]
                    ):
                        raise AccessDenied(
                            "Search hit differs from its observed source", code="EVIDENCE_UNAVAILABLE"
                        )
                    from koinon.knowledge.evidence_capture import document_reference

                    source_reference = document_reference(
                        observed, asset_id=asset.id, source_id=source.id, title=asset.name[:255]
                    ).model_dump(mode="json")
                elif any(row.workspace_id == native_workspace for row in _capture.documents.values()):
                    raise AccessDenied(
                        "Search hit has no matching source observation", code="EVIDENCE_UNAVAILABLE"
                    )
                hits.append(
                    {
                        "id": identifier,
                        "title": asset.name,
                        "text": hit.get("content", ""),
                        "score": hit.get("score", 0),
                        "asset_id": asset.id,
                        "source_id": source.id,
                        "source_reference": source_reference,
                    }
                )
            for citation in result.get("citations", []):
                if citation.get("source_kind") == "knowledge_version":
                    proof = _capture.knowledge_sources.get(str(citation.get("chunk_id")))
                    if citation.get("source_id") not in knowledge or proof is None:
                        raise AccessDenied("Answer cited unadmitted knowledge", code="DOMAIN_SCOPE_MISMATCH")
                    citations.append(
                        {
                            **citation,
                            "asset_id": proof.asset_id,
                            "source_id": None,
                            "kind": "knowledge_version",
                            "knowledge_item_id": proof.asset_id,
                            "knowledge_version_id": proof.knowledge_version_id,
                            "knowledge_version": proof.knowledge_version,
                        }
                    )
                    continue
                if citation.get("source_id") not in admitted:
                    raise AccessDenied("Answer cited an unadmitted source", code="DOMAIN_SCOPE_MISMATCH")
                asset, source = admitted[citation["source_id"]]
                citations.append({**citation, "asset_id": asset.id, "source_id": source.id})
            if result.get("answer"):
                answers.append(result["answer"])
        response: dict = {"hits": sorted(hits, key=lambda hit: hit.get("score") or 0, reverse=True)[:limit]}
        if answer:
            response.update(answer="\n\n".join(answers), citations=citations)
        response["knowledge_settings_snapshot"] = policy.model_dump(mode="json")
        return response

    async def query(
        self,
        subject,
        tenant_id,
        *,
        dataset_id,
        question,
        conversation_id=None,
        sql=None,
        _capture: NativeEvidenceReceipt | None = None,
    ):
        chain = await self._chain(subject, tenant_id, dataset_id, "query:execute")
        if chain[0].kind != "dataset":
            raise InvalidHierarchy("Select a dataset", code="INVALID_DATASET")
        self._ready_dataset(chain[0])
        binding = await self.binding(tenant_id, dataset_id, "structured", entry=chain[0])
        policy = await settings_for_operation(self.knowledge_settings, subject, tenant_id)
        _capture = _capture or NativeEvidenceReceipt(subject, tenant_id)

        async def authorize_model():
            current = await self._chain(subject, tenant_id, dataset_id, "query:execute")
            self._ready_dataset(current[0])

        _capture.authorize_model = authorize_model
        result = await self.domains.query(
            tenant_id=tenant_id,
            workspace_id=binding.native_workspace_id,
            catalog_workspace_id=chain[0].workspace_id,
            dataset_id=binding.native_id,
            dataset_allowlist={binding.native_id},
            question=question,
            conversation_id=conversation_id,
            sql=sql,
            actor=subject,
            _knowledge_settings_snapshot=policy,
            **({"_capture": _capture} if _capture is not None else {}),
        )
        return {**result, "knowledge_settings_snapshot": policy.model_dump(mode="json")}

    async def schema(self, subject, tenant_id, dataset_id, *, _capture: NativeEvidenceReceipt | None = None):
        chain = await self._chain(subject, tenant_id, dataset_id)
        if chain[0].kind != "dataset":
            raise InvalidHierarchy("Select a dataset", code="INVALID_DATASET")
        self._ready_dataset(chain[0])
        binding = await self.binding(tenant_id, dataset_id, "structured", entry=chain[0])
        result = await self.domains.schema(
            tenant_id=tenant_id,
            workspace_id=binding.native_workspace_id,
            dataset_id=binding.native_id,
            actor=subject,
            **({"_capture": _capture} if _capture is not None else {}),
        )
        table_ids = {}
        for table in await self.catalog.list(subject, tenant_id, kind="table", parent_id=dataset_id):
            await self._chain(subject, tenant_id, table.id)
            native = await self.binding(tenant_id, table.id, "structured", entry=table)
            table_ids[native.native_id] = table.id
        for table in result.get("tables", []):
            if str(table["id"]) not in table_ids:
                raise AccessDenied("Schema returned an unadmitted table", code="DOMAIN_SCOPE_MISMATCH")
            table["id"] = table_ids[str(table["id"])]
        return result

    @staticmethod
    def _ready_dataset(dataset):
        if dataset.status != "ready" or dataset.metadata_json.get("_koinon_intake"):
            raise ConflictException(
                "Dataset intake is unfinished; reconcile the retained file version before querying",
                code="DATASET_NOT_READY",
            )

    async def _document(self, subject, tenant_id, document_id):
        chain = await self._chain(subject, tenant_id, document_id)
        if chain[0].kind != "document":
            raise InvalidHierarchy("Select a document", code="INVALID_DOCUMENT")
        return chain, await self.binding(tenant_id, document_id, "canon", entry=chain[0])

    async def document_chunks(
        self, subject, tenant_id, document_id, *, offset=0, limit=50, page=None, section=None, q=None
    ):
        chain, binding = await self._document(subject, tenant_id, document_id)
        if (
            not 0 <= offset <= 100000
            or not 1 <= limit <= 100
            or (page is not None and page < 1)
            or (section is not None and len(section) > 256)
            or (q is not None and len(q) > 512)
        ):
            raise InvalidRequestException("Invalid chunk pagination or filters", code="INVALID_CHUNK_FILTER")
        result = await self.domains.document_chunks(
            tenant_id=tenant_id,
            workspace_id=binding.native_workspace_id,
            source_id=binding.native_id,
            actor=subject,
            offset=offset,
            limit=limit,
            page=page,
            section=section,
            q=q,
        )
        return {
            **result,
            "document_id": document_id,
            "source_id": chain[1].id,
            "native_source_id": binding.native_id,
        }

    async def document_original(self, subject, tenant_id, document_id):
        _, binding = await self._document(subject, tenant_id, document_id)
        return await self.domains.document_original(
            tenant_id=tenant_id,
            workspace_id=binding.native_workspace_id,
            source_id=binding.native_id,
            actor=subject,
            max_bytes=self.settings.max_upload_bytes,
        )

    async def lineage(self, subject, tenant_id, asset_id=None):
        entries = (
            [*await self._chain(subject, tenant_id, asset_id)]
            if asset_id
            else await self.catalog.list(subject, tenant_id)
        )
        nodes, edges = {}, []
        for entry in entries:
            await self._chain(subject, tenant_id, entry.id)
            nodes[entry.id] = {"id": entry.id, "label": entry.name, "kind": entry.kind}
            if entry.parent_id:
                edges.append({"source": entry.parent_id, "target": entry.id, "label": "contains"})
        if asset_id and entries[0].kind in {"document", "dataset"}:
            asset = entries[0]
            domain = "canon" if asset.kind == "document" else "structured"
            binding = await self.binding(tenant_id, asset_id, domain, entry=asset)
            retained = await self.domains.lineage(
                domain=domain,
                tenant_id=tenant_id,
                workspace_id=binding.native_workspace_id,
                native_id=binding.native_id,
                entity_kind=asset.kind,
                actor=subject,
                limit=self.settings.max_lineage_nodes,
            )
            table_ids = {}
            if asset.kind == "dataset":
                for table in await self.catalog.list(subject, tenant_id, kind="table", parent_id=asset_id):
                    await self._chain(subject, tenant_id, table.id)
                    native = await self.binding(tenant_id, table.id, domain, entry=table)
                    table_ids[native.native_id] = table.id
            replacements = {"$asset": asset_id}
            for node in retained.get("nodes", []):
                identifier = node["id"]
                if node["kind"] == "table":
                    if node.get("native_id") not in table_ids:
                        raise AccessDenied(
                            "Lineage returned an unadmitted table", code="DOMAIN_SCOPE_MISMATCH"
                        )
                    replacements[identifier] = table_ids[node["native_id"]]
                    identifier = replacements[identifier]
                nodes[identifier] = {**node, "id": identifier}
            edges.extend(
                {
                    **edge,
                    "source": replacements.get(edge["source"], edge["source"]),
                    "target": replacements.get(edge["target"], edge["target"]),
                }
                for edge in retained.get("edges", [])
            )
        admitted = set(list(nodes)[: self.settings.max_lineage_nodes])
        return {
            "nodes": [node for key, node in nodes.items() if key in admitted],
            "edges": [edge for edge in edges if edge["source"] in admitted and edge["target"] in admitted],
        }

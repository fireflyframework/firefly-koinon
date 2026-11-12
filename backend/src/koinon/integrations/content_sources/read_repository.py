# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Resolve immutable imports in bounded primary reads; never contact a provider here."""

from types import SimpleNamespace
from typing import Literal, cast

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import cast as sql_cast
from sqlalchemy import func, literal, or_, select, true, tuple_
from sqlalchemy.dialects.postgresql import JSONB

from koinon.integrations.content_sources.dtos import Provider
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.read_dtos import (
    LocalFolderSourcePin,
    LocalSourcePin,
    ResolvedFolderSourceOrigin,
    ResolvedSourceOrigin,
)
from koinon.integrations.content_sources.reader_access import RemoteFolderReadTarget, RemoteReadTarget
from koinon.integrations.content_sources.sync_entities import (
    SourceFolderBinding,
    SourceFolderPublication,
    SourceImportedAsset,
    SourceImportedVersion,
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.jobs.entities import Job  # noqa: F401 -- sync runs reference canonical job metadata
from koinon.knowledge.bulk.entities import BulkItem  # noqa: F401 -- source attempts reference intake metadata
from koinon.knowledge.entities import DomainBinding


@repository(name="content_sources.read_repository")
class SourceReadRepository(Repository[SourceImportedAsset, str]):
    def _json_type(self, document, *path):
        if self._require_session().get_bind().dialect.name == "sqlite":
            return func.json_type(document, "$." + ".".join(path))
        selected = sql_cast(document, JSONB)
        for name in path:
            selected = selected[name]
        return func.jsonb_typeof(selected)

    def _values(self, document, *path):
        if self._require_session().get_bind().dialect.name == "sqlite":
            selected = func.json_extract(document, "$." + ".".join(path)) if path else document
            return func.json_each(selected).table_valued("value")
        selected = sql_cast(document, JSONB)
        for name in path:
            selected = selected[name]
        return func.jsonb_array_elements(selected).table_valued("value").lateral()

    def _text(self, document, name):
        if self._require_session().get_bind().dialect.name == "sqlite":
            return func.json_extract(document, "$." + name)
        return sql_cast(document, JSONB)[name].astext

    async def curated_state(self, tenant, identifier):
        from koinon.knowledge.curated.entities import CuratedCatalogState

        value = await self._require_session().scalar(
            select(CuratedCatalogState).where(
                CuratedCatalogState.tenant_id == tenant, CuratedCatalogState.item_id == identifier
            )
        )
        if value is None:
            raise SourceError("access_denied")
        return value

    async def review_references(self, tenant, identifier, owner):
        from koinon.evidence.entities import EvidenceReview

        review = EvidenceReview
        memory = (
            await self._require_session().execute(
                select(review.id, review.snapshot_json["memory_bindings"]).where(
                    review.id == identifier, review.tenant_id == tenant, review.owner_subject == owner
                )
            )
        ).first()
        if memory is None:
            raise SourceError("access_denied")
        values = self._values(review.manifest_json)
        fields = (
            "id",
            "asset_id",
            "kind",
            "source_version_id",
            "extraction_id",
            "source_part_id",
            "snapshot_id",
            "query_id",
            "knowledge_version_id",
        )
        rows = (
            (
                await self._require_session().execute(
                    select(*(self._text(values.c.value, name).label(name) for name in fields))
                    .select_from(review)
                    .join(values, true())
                    .where(review.id == identifier, review.tenant_id == tenant, review.owner_subject == owner)
                    .limit(501)
                )
            )
            .mappings()
            .all()
        )
        if len(rows) > 500:
            raise SourceError("size_exceeded")
        return tuple(SimpleNamespace(**dict(row)) for row in rows), memory[1] or ()

    async def run_references(self, tenant, identifiers, owner):
        from koinon.assistants.entities import ChatRun, ChatThread, ToolResult
        from koinon.assistants.memory.entities import ChatMemoryManifest

        if len(identifiers) > 100:
            raise SourceError("size_exceeded")
        selected = tuple(
            await self._require_session().scalars(
                select(ChatRun.id)
                .join(ChatThread, ChatThread.id == ChatRun.thread_id)
                .where(
                    ChatRun.tenant_id == tenant,
                    ChatThread.tenant_id == tenant,
                    ChatThread.subject == owner,
                    ChatRun.id.in_(identifiers),
                )
            )
        )
        if set(selected) != set(identifiers):
            raise SourceError("access_denied")
        results = (
            await self._require_session().execute(
                select(
                    ToolResult.id,
                    ToolResult.run_id,
                    ToolResult.kind,
                    ToolResult.payload["generation"]["status"].as_string(),
                )
                .where(ToolResult.run_id.in_(selected))
                .limit(2001)
            )
        ).all()
        if len(results) > 2000:
            raise SourceError("size_exceeded")
        sources = await self.result_references(
            tenant,
            tuple(row[0] for row in results),
            owner=owner,
            expected_runs={row[0]: row[1] for row in results},
        )
        row = ChatMemoryManifest
        manifests = (
            await self._require_session().execute(
                select(row.run_id, row.generation_id, row.manifest_sha256)
                .where(row.tenant_id == tenant, row.subject == owner, row.run_id.in_(selected))
                .limit(201)
            )
        ).all()
        if len(manifests) > 200:
            raise SourceError("size_exceeded")
        known_generations = {row[1] for row in manifests}
        if any(
            kind == "generation" and status != "started" and identifier not in known_generations
            for identifier, _, kind, status in results
        ):
            raise SourceError("unavailable")
        bindings = tuple(
            SimpleNamespace(run_id=run, generation_id=generation, manifest_sha256=digest, results=())
            for run, generation, digest in manifests
        )
        return sources, bindings

    async def mutation_entries(self, tenant, identifiers):
        from koinon.catalog.entities import CatalogEntry

        entry = CatalogEntry
        branch = (
            select(entry.id, literal(0).label("depth"))
            .where(entry.tenant_id == tenant, entry.id.in_(identifiers))
            .cte("reader_mutation_branch", recursive=True)
        )
        branch = branch.union_all(
            select(entry.id, branch.c.depth + 1)
            .join(branch, entry.parent_id == branch.c.id)
            .where(entry.tenant_id == tenant, branch.c.depth < 16)
        )
        result = tuple(await self._require_session().scalars(select(branch.c.id).distinct().limit(1001)))
        if len(result) > 1000:
            raise SourceError("size_exceeded")
        return result

    async def curated_entry_references(self, tenant, identifiers):
        from koinon.knowledge.curated.entities import CuratedCatalogState

        state = CuratedCatalogState
        rows = (
            await self._require_session().execute(
                select(
                    state.item_id,
                    func.coalesce(state.serving_version_id, state.head_version_id),
                )
                .where(state.tenant_id == tenant, state.item_id.in_(identifiers))
                .limit(1001)
            )
        ).all()
        if len(rows) > 1000:
            raise SourceError("size_exceeded")
        return tuple(
            SimpleNamespace(
                asset_id=asset,
                kind="knowledge_version",
                knowledge_version_id=version,
                source_version_id=None,
                extraction_id=None,
                source_part_id=None,
                snapshot_id=None,
                query_id=None,
            )
            for asset, version in rows
        )

    async def search_candidates(self, tenant, *, workspace_id=None, project_id=None, collection_id=None):
        from koinon.catalog.entities import CatalogEntry

        entry = CatalogEntry
        statement = select(entry.id).where(
            entry.tenant_id == tenant, entry.kind.in_(("document", "knowledge_item"))
        )
        if workspace_id:
            statement = statement.where(entry.workspace_id == workspace_id)
        if project_id:
            statement = statement.where(entry.project_id == project_id)
        if collection_id:
            branch = (
                select(entry.id, literal(0).label("depth"))
                .where(entry.tenant_id == tenant, entry.id == collection_id)
                .cte("reader_search_branch", recursive=True)
            )
            branch = branch.union_all(
                select(entry.id, branch.c.depth + 1)
                .join(branch, entry.parent_id == branch.c.id)
                .where(entry.tenant_id == tenant, branch.c.depth < 16)
            )
            statement = statement.where(entry.id.in_(select(branch.c.id)))
        rows = tuple(await self._require_session().scalars(statement.order_by(entry.id).limit(1001)))
        if len(rows) > 1000:
            raise SourceError("size_exceeded")
        return rows

    async def memory_references(self, tenant, bindings, owner):
        from koinon.assistants.memory.entities import ChatMemoryManifest

        if len(bindings) > 200:
            raise SourceError("size_exceeded")
        wanted = {
            binding.generation_id: binding.manifest_sha256 for binding in bindings if binding.generation_id
        }
        results = {pin.id for binding in bindings for pin in binding.results}
        expected_runs = {pin.id: binding.run_id for binding in bindings for pin in binding.results}
        if wanted:
            row = ChatMemoryManifest
            rows = (
                await self._require_session().execute(
                    select(
                        row.generation_id,
                        row.manifest_sha256,
                        row.run_id,
                    ).where(row.tenant_id == tenant, row.subject == owner, row.generation_id.in_(wanted))
                )
            ).all()
            expected_generations = {
                binding.generation_id: binding.run_id for binding in bindings if binding.generation_id
            }
            if len(rows) != len(wanted) or any(
                digest != wanted[generation] or run != expected_generations[generation]
                for generation, digest, run, *_ in rows
            ):
                raise SourceError("authority_changed")
            for path in ("dependencies", "turns"):
                dependencies = self._values(row.manifest_json, path)
                pins = self._values(dependencies.c.value, "result_pins")
                referenced = (
                    await self._require_session().execute(
                        select(self._text(dependencies.c.value, "run_id"), self._text(pins.c.value, "id"))
                        .select_from(row)
                        .join(dependencies, true())
                        .join(pins, true())
                        .where(row.tenant_id == tenant, row.subject == owner, row.generation_id.in_(wanted))
                        .limit(2001)
                    )
                ).all()
                if len(referenced) > 2000:
                    raise SourceError("size_exceeded")
                for run, identifier in referenced:
                    if (
                        not run
                        or not identifier
                        or identifier in expected_runs
                        and expected_runs[identifier] != run
                    ):
                        raise SourceError("authority_changed")
                    results.add(identifier)
                    expected_runs[identifier] = run
        return await self.result_references(tenant, results, owner=owner, expected_runs=expected_runs)

    async def result_references(self, tenant, identifiers, *, owner=None, expected_runs=None):
        from koinon.assistants.entities import ChatRun, ChatThread, ToolResult

        if len(identifiers) > 2000:
            raise SourceError("size_exceeded")
        if not identifiers:
            return ()
        statement = (
            select(ToolResult.id, ToolResult.run_id)
            .join(ChatRun, ChatRun.id == ToolResult.run_id)
            .join(ChatThread, ChatThread.id == ChatRun.thread_id)
            .where(
                ChatRun.tenant_id == tenant, ChatThread.tenant_id == tenant, ToolResult.id.in_(identifiers)
            )
        )
        if owner is not None:
            statement = statement.where(ChatThread.subject == owner)
        identities = (await self._require_session().execute(statement)).all()
        expected_runs = expected_runs or {}
        if {row[0] for row in identities} != set(identifiers) or any(
            identifier in expected_runs and run != expected_runs[identifier] for identifier, run in identities
        ):
            raise SourceError("access_denied")
        incomplete = await self._require_session().scalar(
            select(ToolResult.id)
            .where(
                ToolResult.id.in_(identifiers),
                ToolResult.kind.in_(("search", "query", "schema", "lineage")),
                ToolResult.payload["source_manifest"]["complete"].as_boolean().is_distinct_from(True),
            )
            .limit(1)
        )
        if incomplete is not None:
            raise SourceError("unavailable")
        shapes = (
            await self._require_session().execute(
                select(
                    ToolResult.kind,
                    self._json_type(ToolResult.payload, "source_manifest", "sources"),
                    self._json_type(ToolResult.payload, "release", "source_refs"),
                ).where(ToolResult.id.in_(identifiers))
            )
        ).all()
        for kind, sources, release in shapes:
            if (
                (kind in ("search", "query", "schema", "lineage") and sources != "array")
                or sources not in (None, "array")
                or release not in (None, "array")
            ):
                raise SourceError("unavailable")
        fields = (
            "id",
            "asset_id",
            "kind",
            "source_version_id",
            "extraction_id",
            "source_part_id",
            "snapshot_id",
            "query_id",
            "knowledge_version_id",
        )
        rows = []
        for path in (("source_manifest", "sources"), ("release", "source_refs")):
            values = self._values(ToolResult.payload, *path)
            rows.extend(
                (
                    await self._require_session().execute(
                        select(*(self._text(values.c.value, name).label(name) for name in fields))
                        .select_from(ToolResult)
                        .join(ChatRun, ChatRun.id == ToolResult.run_id)
                        .join(values, true())
                        .where(ChatRun.tenant_id == tenant, ToolResult.id.in_(identifiers))
                        .limit(501)
                    )
                )
                .mappings()
                .all()
            )
        if len(rows) > 500:
            raise SourceError("size_exceeded")
        if any(
            row["kind"] not in ("document", "dataset", "knowledge_version")
            or not isinstance(row["asset_id"], str)
            or not row["asset_id"]
            or not isinstance(row["id"], str)
            or not row["id"]
            for row in rows
        ):
            raise SourceError("unavailable")
        return tuple(SimpleNamespace(**dict(row)) for row in rows)

    async def reference_context(self, tenant, reference):
        from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot

        session = self._require_session()
        if reference.kind == "knowledge_version":
            state = await session.scalar(
                select(CuratedCatalogState).where(
                    CuratedCatalogState.tenant_id == tenant, CuratedCatalogState.item_id == reference.asset_id
                )
            )
            roots = set(
                await session.scalars(
                    select(CuratedSourceRoot.source_asset_id).where(
                        CuratedSourceRoot.tenant_id == tenant,
                        CuratedSourceRoot.item_id == reference.asset_id,
                        CuratedSourceRoot.native_version_id == reference.knowledge_version_id,
                    )
                )
            )
            if roots and state is None:
                raise SourceError("unavailable")
            return state, roots
        marker = await session.scalar(
            select(SourceImportedAsset.asset_id).where(
                SourceImportedAsset.tenant_id == tenant, SourceImportedAsset.asset_id == reference.asset_id
            )
        )
        if marker is None:
            return None, None
        binding = await session.scalar(
            select(DomainBinding).where(
                DomainBinding.tenant_id == tenant,
                DomainBinding.catalog_id == reference.asset_id,
                DomainBinding.domain == ("canon" if reference.kind == "document" else "structured"),
            )
        )
        if binding is None:
            raise SourceError("unavailable")
        return binding, True

    async def reference_pins(self, tenant, reference, binding, snapshots=()):
        from koinon.integrations.content_sources.read_dtos import LocalSourcePin

        if reference.kind == "document":
            if not reference.source_version_id or not reference.extraction_id:
                raise SourceError("unavailable")
            return (
                LocalSourcePin(
                    reference.asset_id,
                    "canon",
                    binding.native_workspace_id,
                    binding.native_id,
                    reference.source_version_id,
                    reference.extraction_id,
                    reference.source_part_id,
                ),
            )
        if not snapshots:
            raise SourceError("unavailable")
        rows = (
            await self._require_session().execute(
                select(SourceImportedVersion, SourceImportAttempt.receipt_json)
                .join(SourceImportAttempt, SourceImportAttempt.id == SourceImportedVersion.attempt_id)
                .where(
                    SourceImportedVersion.tenant_id == tenant,
                    SourceImportAttempt.tenant_id == tenant,
                    SourceImportedVersion.asset_id == reference.asset_id,
                    SourceImportedVersion.domain == "structured",
                )
                .limit(1001)
            )
        ).all()
        if len(rows) > 1000:
            raise SourceError("size_exceeded")
        covered, pins = set(), []
        for row, receipt in rows:
            matching = set(snapshots) & {
                str(table.get("snapshot_id")) for table in (receipt or {}).get("tables", [])
            }
            if matching:
                covered.update(matching)
                pins.append(
                    LocalSourcePin(
                        row.asset_id,
                        "structured",
                        row.native_workspace_id,
                        row.native_source_id,
                        row.native_version_id,
                    )
                )
        if covered != set(snapshots):
            raise SourceError("unavailable")
        return tuple(pins)

    async def expected_extractions(self, tenant, pins):
        imported = select(SourceImportedAsset.asset_id).where(SourceImportedAsset.tenant_id == tenant)
        rows = list(
            await self._require_session().scalars(
                select(SourceImportedVersion).where(
                    SourceImportedVersion.tenant_id == tenant,
                    SourceImportedVersion.asset_id.in_(imported),
                    SourceImportedVersion.domain == "canon",
                    tuple_(
                        SourceImportedVersion.asset_id,
                        SourceImportedVersion.native_workspace_id,
                        SourceImportedVersion.native_source_id,
                        SourceImportedVersion.native_version_id,
                    ).in_(
                        [
                            (pin.asset_id, pin.native_workspace_id, pin.native_source_id, pin.version_id)
                            for pin in pins
                            if isinstance(pin, LocalSourcePin) and pin.domain == "canon"
                        ]
                    ),
                )
            )
        )
        return {
            (
                row.asset_id,
                row.native_workspace_id,
                row.native_source_id,
                row.native_version_id,
            ): row.extraction_id
            for row in rows
        }

    @staticmethod
    def _entry_ancestors(tenant, identifiers):
        from koinon.catalog.entities import CatalogEntry

        ancestors = (
            select(CatalogEntry.id, CatalogEntry.parent_id, literal(0).label("depth"))
            .where(CatalogEntry.tenant_id == tenant, CatalogEntry.id.in_(identifiers))
            .cte("source_entry_ancestors", recursive=True)
        )
        return ancestors.union_all(
            select(CatalogEntry.id, CatalogEntry.parent_id, ancestors.c.depth + 1)
            .join(ancestors, CatalogEntry.id == ancestors.c.parent_id)
            .where(CatalogEntry.tenant_id == tenant, ancestors.c.depth < 16)
        )

    async def folder_pins(self, tenant, identifiers):
        ancestors = self._entry_ancestors(tenant, identifiers)
        folder = SourceFolderPublication
        latest = (
            select(folder.local_folder_id, func.max(folder.canonical_revision).label("revision"))
            .where(folder.tenant_id == tenant, folder.local_folder_id.in_(select(ancestors.c.id)))
            .group_by(folder.local_folder_id)
            .subquery()
        )
        folder_rows = (
            await self._require_session().execute(
                select(folder.local_folder_id, folder.id, folder.observation_id, folder.canonical_revision)
                .join(
                    latest,
                    (folder.local_folder_id == latest.c.local_folder_id)
                    & (folder.canonical_revision == latest.c.revision),
                )
                .where(folder.tenant_id == tenant)
                .order_by(folder.local_folder_id)
                .limit(1001)
            )
        ).all()
        if len(folder_rows) > 1000:
            raise SourceError("size_exceeded")
        return tuple(LocalFolderSourcePin(*row) for row in folder_rows)

    async def entry_read_state(self, tenant, identifiers):
        """Pin classification and placement without selecting canonical payload columns."""
        from koinon.catalog.entities import CatalogEntry

        if len(identifiers) > 1000:
            raise SourceError("size_exceeded")
        entry = CatalogEntry
        ancestors = self._entry_ancestors(tenant, identifiers)
        rows = tuple(
            (
                await self._require_session().execute(
                    select(
                        entry.id,
                        entry.parent_id,
                        entry.kind,
                        entry.workspace_id,
                        entry.project_id,
                        entry.status,
                        entry.mutation_revision,
                    )
                    .where(entry.tenant_id == tenant, entry.id.in_(select(ancestors.c.id)))
                    .order_by(entry.id)
                    .limit(16001)
                )
            ).all()
        )
        if len(rows) > 16000:
            raise SourceError("size_exceeded")
        by_id = {row.id: row for row in rows}
        for identifier in identifiers:
            seen = set()
            while identifier is not None:
                if identifier not in by_id or identifier in seen or len(seen) >= 16:
                    raise SourceError("access_denied")
                seen.add(identifier)
                identifier = by_id[identifier].parent_id
        return rows

    async def entry_pins(self, tenant, identifiers, *, version_id=None):
        session = self._require_session()
        ancestors = self._entry_ancestors(tenant, identifiers)
        folder_pins = await self.folder_pins(tenant, identifiers)
        markers = list(
            await session.scalars(
                select(SourceImportedAsset)
                .where(
                    SourceImportedAsset.tenant_id == tenant,
                    or_(
                        SourceImportedAsset.asset_id.in_(select(ancestors.c.id)),
                        SourceImportedAsset.source_id.in_(select(ancestors.c.id)),
                    ),
                )
                .limit(1001)
            )
        )
        if len(markers) > 1000:
            raise SourceError("size_exceeded")
        if not markers:
            return folder_pins
        assets = {marker.asset_id for marker in markers}
        statement = (
            select(SourceImportedVersion)
            .join(SourceImportAttempt, SourceImportAttempt.id == SourceImportedVersion.attempt_id)
            .join(SourceObject, SourceObject.id == SourceImportAttempt.object_id)
            .where(
                SourceImportedVersion.tenant_id == tenant,
                SourceImportAttempt.tenant_id == tenant,
                SourceObject.tenant_id == tenant,
                SourceImportedVersion.asset_id.in_(assets),
            )
        )
        if version_id is not None:
            statement = statement.where(SourceImportedVersion.native_version_id == version_id)
        else:
            statement = statement.where(SourceImportAttempt.generation == SourceObject.generation)
        rows = list(await session.scalars(statement.limit(1001)))
        if len(rows) > 1000 or {row.asset_id for row in rows} != assets:
            raise SourceError("unavailable")
        return folder_pins + tuple(
            LocalSourcePin(
                row.asset_id,
                cast(Literal["canon", "structured"], row.domain),
                row.native_workspace_id,
                row.native_source_id,
                row.native_version_id,
                row.extraction_id,
            )
            for row in rows
        )

    async def _resolve_folders(self, tenant, pins):
        """Compare retained evidence using identity columns only, before canonical payload reads."""
        from koinon.integrations.content_sources.read_authority import source_authority
        from koinon.integrations.content_sources.sync_checkpoints import event_hash

        if not pins:
            return ()
        session = self._require_session()
        publication, observation, work = SourceFolderPublication, SourceSyncObservation, SourceSyncWork
        pins = tuple(dict.fromkeys(pins))
        if len(pins) > 1000:
            raise SourceError("size_exceeded")
        rows = (
            await session.execute(
                select(
                    publication,
                    observation,
                    work,
                    SourceObject,
                    SourceMapping,
                    PersonalSourceConnection,
                    SourceMappingPolicy,
                    SourceFolderBinding,
                )
                .join(observation, observation.id == publication.observation_id)
                .join(work, work.id == publication.work_id)
                .join(SourceObject, SourceObject.id == publication.object_id)
                .join(SourceMapping, SourceMapping.id == publication.mapping_id)
                .join(PersonalSourceConnection, PersonalSourceConnection.id == SourceMapping.connection_id)
                .join(SourceSyncState, SourceSyncState.mapping_id == SourceMapping.id)
                .join(SourceMappingPolicy, SourceMappingPolicy.id == SourceSyncState.accepted_policy_id)
                .join(
                    SourceFolderBinding,
                    (SourceFolderBinding.tenant_id == publication.tenant_id)
                    & (SourceFolderBinding.mapping_id == publication.mapping_id)
                    & (SourceFolderBinding.local_folder_id == publication.local_folder_id),
                )
                .where(
                    publication.tenant_id == tenant, publication.id.in_([pin.publication_id for pin in pins])
                )
                .limit(1001)
                .execution_options(populate_existing=True)
            )
        ).all()
        indexed = {row[0].id: row for row in rows}
        if len(rows) != len(indexed) or len(rows) > 1000:
            raise SourceError("unavailable")
        folder_ids = tuple(dict.fromkeys(pin.folder_id for pin in pins))
        latest = dict(
            (
                await session.execute(
                    select(publication.local_folder_id, func.max(publication.canonical_revision))
                    .where(publication.tenant_id == tenant, publication.local_folder_id.in_(folder_ids))
                    .group_by(publication.local_folder_id)
                )
            ).all()
        )
        identities = await self.entry_read_state(tenant, folder_ids)
        identity_by_id = {row.id: row for row in identities}
        result = []
        for pin in pins:
            row = indexed.get(pin.publication_id)
            if row is None:
                raise SourceError("unavailable")
            published, observed, pending, obj, mapping, importer, policy, binding = row
            if (
                published.local_folder_id != pin.folder_id
                or published.observation_id != pin.observation_id
                or published.canonical_revision != pin.canonical_revision
            ):
                raise SourceError("unavailable")
            if any(value.tenant_id != tenant for value in row):
                raise SourceError("access_denied")
            authority, digest = source_authority(importer)
            if (
                policy.accepted_at is None
                or policy.accepted_by != mapping.owner
                or policy.owner != mapping.owner
                or policy.mapping_revision != mapping.revision
                or policy.authority_sha256 != digest
                or not isinstance(policy.policy_json, dict)
                or policy.policy_json.get("authority") != authority
            ):
                raise SourceError("authority_changed")
            event = observed.event_json
            if not isinstance(event, dict):
                raise SourceError("unavailable")
            prior = event.get("item", {})
            ancestry = event.get("ancestry", [])
            if (
                not isinstance(prior, dict)
                or prior.get("kind") != "folder"
                or not isinstance(ancestry, list)
                or not ancestry
                or any(not isinstance(value, str) or not value for value in ancestry)
                or not isinstance(prior.get("parents"), list)
                or len(prior["parents"]) != 1
                or prior["parents"][0] != ancestry[-1]
                or observed.event_sha256 != event_hash(event)
                or pending.event_sha256 != observed.event_sha256
                or observed.remote_version is None
                or prior.get("version") != observed.remote_version
                or prior.get("item_id") != obj.item_id
                or prior.get("scope")
                != {
                    "drive_id": mapping.drive_id,
                    "account": {
                        "provider": mapping.provider,
                        "subject": mapping.external_subject,
                        "tenant_id": mapping.external_tenant,
                    },
                }
            ):
                raise SourceError("unavailable")
            if (
                mapping.status not in {"active", "paused"}
                or importer.status != "connected"
                or importer.owner != mapping.owner
                or (
                    importer.provider,
                    importer.external_subject,
                    importer.external_tenant,
                    importer.issuer,
                    importer.config_fingerprint,
                )
                != (
                    mapping.provider,
                    mapping.external_subject,
                    mapping.external_tenant,
                    mapping.issuer,
                    mapping.config_fingerprint,
                )
                or obj.mapping_revision != mapping.revision
                or obj.mapping_id != mapping.id
                or obj.state not in {"imported", "pending", "failed"}
                or obj.remote_kind != "folder"
                or obj.remote_name != prior.get("name")
                or obj.remote_parent_id != prior["parents"][0]
                or obj.remote_ancestry_json != ancestry
                or obj.generation != observed.generation
                or obj.remote_version != observed.remote_version
                or pending.generation != observed.generation
                or pending.remote_version != observed.remote_version
                or obj.published_native_version_id is not None
                or obj.published_local_revision != str(pin.canonical_revision)
                or obj.published_sha256 != published.canonical_sha256
                or binding.remote_folder_id != obj.item_id
                or binding.local_parent_id != published.local_parent_id
                or binding.remote_parent_id != prior["parents"][0]
                or binding.ancestry_json != ancestry
            ):
                raise SourceError("version_changed")
            if latest.get(pin.folder_id) != pin.canonical_revision:
                raise SourceError("version_changed")
            current = identity_by_id.get(pin.folder_id)
            if (
                current is None
                or current.kind not in {"folder", "collection", "corpus"}
                or current.parent_id != published.local_parent_id
                or current.mutation_revision != pin.canonical_revision
                or current.workspace_id != mapping.workspace_id
                or current.project_id != mapping.project_id
            ):
                raise SourceError("version_changed")
            try:
                target = RemoteFolderReadTarget(
                    cast(Provider, mapping.provider),
                    mapping.drive_id,
                    obj.item_id,
                    observed.remote_version,
                    mapping.external_tenant,
                    name=prior["name"],
                    parents=tuple(prior["parents"]),
                    mime_type=prior["mime_type"],
                    size_bytes=prior.get("size_bytes"),
                    ancestry=tuple(ancestry),
                    root_ancestry=tuple(policy.root_ancestry_json),
                )
            except (KeyError, TypeError, ValueError) as error:
                raise SourceError("unavailable") from error
            result.append(
                ResolvedFolderSourceOrigin(
                    pin,
                    mapping.id,
                    mapping.revision,
                    obj.id,
                    obj.generation,
                    target,
                    mapping.config_fingerprint,
                    policy.id,
                    policy.authority_sha256,
                    binding.revision,
                    identities,
                )
            )
        return tuple(result)

    async def resolve(self, tenant, pins):
        session = self._require_session()
        folder_pins = tuple(pin for pin in pins if isinstance(pin, LocalFolderSourcePin))
        pins = tuple(pin for pin in pins if isinstance(pin, LocalSourcePin))
        # A direct folder or native reference cannot omit its managed ancestors.
        identifiers = tuple(pin.folder_id for pin in folder_pins) + tuple(pin.asset_id for pin in pins)
        inherited = await self.folder_pins(tenant, identifiers) if identifiers else ()
        folder_origins = await self._resolve_folders(tenant, folder_pins + inherited)
        if not pins:
            return folder_origins
        identifiers = {pin.asset_id for pin in pins}
        bindings = list(
            await session.scalars(
                select(DomainBinding).where(
                    DomainBinding.tenant_id == tenant, DomainBinding.catalog_id.in_(identifiers)
                )
            )
        )
        bound = {(row.catalog_id, row.domain): row for row in bindings}
        markers = {
            row.asset_id: row
            for row in await session.scalars(
                select(SourceImportedAsset).where(
                    SourceImportedAsset.tenant_id == tenant, SourceImportedAsset.asset_id.in_(identifiers)
                )
            )
        }
        for pin in pins:
            binding = bound.get((pin.asset_id, pin.domain))
            if (
                binding is None
                or binding.native_workspace_id != pin.native_workspace_id
                or (pin.domain == "canon" and binding.native_id != pin.native_source_id)
            ):
                raise SourceError("access_denied")
        imported = tuple(pin for pin in pins if pin.asset_id in markers)
        if not imported:
            return folder_origins
        version = SourceImportedVersion
        rows = (
            await session.execute(
                select(version, SourceImportAttempt, SourceMapping, SourceObject, PersonalSourceConnection)
                .join(SourceImportAttempt, SourceImportAttempt.id == version.attempt_id)
                .join(SourceMapping, SourceMapping.id == SourceImportAttempt.mapping_id)
                .join(SourceObject, SourceObject.id == SourceImportAttempt.object_id)
                .join(PersonalSourceConnection, PersonalSourceConnection.id == SourceMapping.connection_id)
                .where(
                    version.tenant_id == tenant,
                    SourceImportAttempt.tenant_id == tenant,
                    SourceMapping.tenant_id == tenant,
                    SourceObject.tenant_id == tenant,
                    PersonalSourceConnection.tenant_id == tenant,
                    tuple_(
                        version.asset_id,
                        version.domain,
                        version.native_workspace_id,
                        version.native_source_id,
                        version.native_version_id,
                    ).in_(
                        [
                            (
                                pin.asset_id,
                                pin.domain,
                                pin.native_workspace_id,
                                pin.native_source_id,
                                pin.version_id,
                            )
                            for pin in imported
                        ]
                    ),
                )
            )
        ).all()
        versions = {}
        for receipt, attempt, mapping, obj, importer in rows:
            key = (
                receipt.asset_id,
                receipt.domain,
                receipt.native_workspace_id,
                receipt.native_source_id,
                receipt.native_version_id,
            )
            if key in versions:
                raise SourceError("unavailable")
            versions[key] = (receipt, attempt, mapping, obj, importer)
        result = []
        policies = {}
        for policy, state in (
            await session.execute(
                select(SourceMappingPolicy, SourceSyncState)
                .join(SourceSyncState, SourceSyncState.accepted_policy_id == SourceMappingPolicy.id)
                .where(
                    SourceMappingPolicy.tenant_id == tenant,
                    SourceSyncState.tenant_id == tenant,
                    SourceSyncState.mapping_id.in_({value[2].id for value in versions.values()}),
                )
            )
        ).all():
            policies[state.mapping_id] = policy
        for pin in imported:
            value = versions.get(
                (pin.asset_id, pin.domain, pin.native_workspace_id, pin.native_source_id, pin.version_id)
            )
            if value is None:
                raise SourceError("unavailable")
            receipt, attempt, mapping, obj, importer = value
            from koinon.integrations.content_sources.read_authority import source_authority

            authority, authority_digest = source_authority(importer)
            policy = policies.get(mapping.id)
            if (
                policy is None
                or policy.accepted_at is None
                or policy.accepted_by != mapping.owner
                or policy.mapping_revision != mapping.revision
                or policy.owner != mapping.owner
                or policy.authority_sha256 != authority_digest
                or policy.policy_json.get("authority") != authority
            ):
                raise SourceError("authority_changed")
            marker = markers[pin.asset_id]
            if obj.generation != attempt.generation or obj.remote_version != attempt.remote_version:
                raise SourceError("version_changed")
            if (
                receipt.extraction_id != pin.extraction_id
                or receipt.native_asset_id != bound[(pin.asset_id, pin.domain)].native_id
                or receipt.source_id != marker.source_id
                or attempt.source_id != marker.source_id
                or attempt.asset_id != pin.asset_id
                or attempt.committed_at is None
                or not attempt.receipt_json
                or mapping.status not in {"active", "paused"}
                or importer.status != "connected"
                or importer.owner != mapping.owner
                or (
                    importer.provider,
                    importer.external_subject,
                    importer.external_tenant,
                    importer.issuer,
                    importer.config_fingerprint,
                )
                != (
                    mapping.provider,
                    mapping.external_subject,
                    mapping.external_tenant,
                    mapping.issuer,
                    mapping.config_fingerprint,
                )
                or mapping.revision != attempt.mapping_revision
                or obj.mapping_id != mapping.id
                or obj.mapping_revision != mapping.revision
                or obj.state not in {"imported", "pending", "failed"}
                or (mapping.provider, mapping.external_tenant, mapping.drive_id)
                != (attempt.provider, attempt.external_tenant, attempt.drive_id)
            ):
                raise SourceError("unavailable")
            result.append(
                ResolvedSourceOrigin(
                    pin,
                    attempt.id,
                    mapping.id,
                    mapping.revision,
                    obj.id,
                    obj.generation,
                    RemoteReadTarget(
                        cast(Provider, attempt.provider),
                        attempt.drive_id,
                        attempt.remote_item_id,
                        attempt.remote_version,
                        attempt.external_tenant,
                    ),
                    mapping.config_fingerprint,
                    policy.id,
                    policy.authority_sha256,
                )
            )
        return folder_origins + tuple(result)

    async def lock_origins(self, tenant, origins, connections):
        from koinon.catalog.entities import CatalogEntry

        session = self._require_session()
        mapping_ids = {origin.mapping_id for origin in origins}
        importer_ids = select(SourceMapping.connection_id).where(
            SourceMapping.tenant_id == tenant, SourceMapping.id.in_(mapping_ids)
        )
        await session.execute(
            select(PersonalSourceConnection.id)
            .where(
                PersonalSourceConnection.tenant_id == tenant,
                or_(
                    PersonalSourceConnection.id.in_([row[0] for row in connections]),
                    PersonalSourceConnection.id.in_(importer_ids),
                ),
            )
            .order_by(PersonalSourceConnection.id)
            .with_for_update()
        )
        for entity, identifiers in (
            (SourceMapping, mapping_ids),
            (SourceObject, {origin.object_id for origin in origins}),
            (
                SourceImportAttempt,
                {origin.attempt_id for origin in origins if isinstance(origin, ResolvedSourceOrigin)},
            ),
        ):
            await session.execute(
                select(entity.id)
                .where(
                    entity.tenant_id == tenant,
                    entity.id.in_(identifiers),
                )
                .order_by(entity.id)
                .with_for_update()
            )
            if entity is SourceMapping and mapping_ids:
                await session.execute(
                    select(SourceSyncState.mapping_id)
                    .where(SourceSyncState.tenant_id == tenant, SourceSyncState.mapping_id.in_(mapping_ids))
                    .order_by(SourceSyncState.mapping_id)
                    .with_for_update()
                )
        folders = tuple(origin for origin in origins if isinstance(origin, ResolvedFolderSourceOrigin))
        if folders:
            await session.execute(
                select(CatalogEntry.id)
                .where(
                    CatalogEntry.tenant_id == tenant,
                    CatalogEntry.id.in_({row.id for origin in folders for row in origin.ancestry}),
                )
                .order_by(CatalogEntry.id)
                .with_for_update()
            )
            await session.execute(
                select(SourceFolderBinding.local_folder_id)
                .where(
                    SourceFolderBinding.tenant_id == tenant,
                    SourceFolderBinding.local_folder_id.in_({origin.pin.folder_id for origin in folders}),
                )
                .order_by(SourceFolderBinding.mapping_id, SourceFolderBinding.remote_folder_id)
                .with_for_update()
            )

    async def check_connections(self, actor, tenant, revisions):
        if not revisions:
            return ()
        rows = list(
            await self._require_session().scalars(
                select(PersonalSourceConnection)
                .where(
                    PersonalSourceConnection.tenant_id == tenant,
                    PersonalSourceConnection.owner == actor,
                    PersonalSourceConnection.id.in_(revisions),
                )
                .order_by(PersonalSourceConnection.id)
                .execution_options(populate_existing=True)
            )
        )
        if len(rows) != len(revisions) or any(
            row.status != "connected"
            or row.revision != revisions[row.id]
            or row.refresh_operation is not None
            for row in rows
        ):
            raise SourceError("authority_changed")
        return tuple(
            (
                row.id,
                row.revision,
                row.provider,
                row.config_fingerprint,
                row.external_subject,
                row.external_tenant,
                row.issuer,
                tuple(row.scopes),
            )
            for row in rows
        )

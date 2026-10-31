# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit retained read admission, backed by native row and catalog ancestry."""

from __future__ import annotations

from uuid import UUID

from pyfly.container import component
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import text

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import native_scope
from koinon.knowledge.bulk_queries.native_repository import NativeQueryRepository
from koinon.knowledge.service import KnowledgeFacade
from koinon.web.capabilities import CapabilityRegistry
from koinon.web.legacy_security import LegacyOperationPolicies

READ_OPERATIONS = (
    ("canon", "/agent/knowledge/{item_id}", "catalog:read"),
    ("canon", "/agent/knowledge/{item_id}/provenance", "catalog:read"),
    ("canon", "/agent/sources/{source_id}", "catalog:read"),
    ("canon", "/audit", "audit:read"),
    ("canon", "/billing", "audit:read"),
    ("canon", "/billing/events", "audit:read"),
    ("canon", "/billing/summary", "audit:read"),
    ("canon", "/billing/top", "audit:read"),
    ("canon", "/billing/by-subject", "audit:read"),
    ("canon", "/billing/latency", "audit:read"),
    ("canon", "/candidates", "catalog:read"),
    ("canon", "/candidates/{candidate_id}", "catalog:read"),
    ("canon", "/conversations/{conversation_id}", "catalog:read"),
    ("canon", "/ingest-jobs", "catalog:read"),
    ("canon", "/ingest-jobs/{job_id}", "catalog:read"),
    ("canon", "/ingest-jobs/{job_id}/stream", "catalog:read"),
    ("canon", "/knowledge", "catalog:read"),
    ("canon", "/knowledge/{item_id}", "catalog:read"),
    ("canon", "/knowledge/{item_id}/history", "catalog:read"),
    ("canon", "/knowledge/{item_id}/provenance", "catalog:read"),
    ("canon", "/knowledge/{item_id}/diff", "catalog:read"),
    ("canon", "/knowledge/{item_id}/relations", "catalog:read"),
    ("canon", "/knowledge:graph", "catalog:read"),
    ("canon", "/knowledge:stale", "catalog:read"),
    ("canon", "/sources/{source_id}", "catalog:read"),
    ("canon", "/sources", "catalog:read"),
    ("canon", "/stats", "catalog:read"),
    ("canon", "/taxonomy", "catalog:read"),
    ("canon", "/version", "catalog:read"),
    ("structured", "/agent/conversations", "catalog:read"),
    ("structured", "/agent/conversations/{conversation_id}", "catalog:read"),
    ("structured", "/agent/datasets", "catalog:read"),
    ("structured", "/agent/datasets/by-name/{name}", "catalog:read"),
    ("structured", "/agent/datasets/{dataset_id}", "catalog:read"),
    ("structured", "/agent/datasets/{dataset_id}/relations", "catalog:read"),
    ("structured", "/agent/datasets/{dataset_id}/tables", "catalog:read"),
    ("structured", "/agent/examples", "catalog:read"),
    ("structured", "/agent/glossary", "catalog:read"),
    ("structured", "/agent/glossary/{term_id}", "catalog:read"),
    ("structured", "/agent/ingest-jobs", "catalog:read"),
    ("structured", "/agent/ingest-jobs/{job_id}", "catalog:read"),
    ("structured", "/agent/ingest-jobs/{job_id}/events", "catalog:read"),
    ("structured", "/agent/ingest-jobs/{job_id}/stream", "catalog:read"),
    ("structured", "/agent/schema-objects/{object_id}", "catalog:read"),
    ("structured", "/agent/semantic/dimensions", "catalog:read"),
    ("structured", "/agent/semantic/dimensions/{dimension_id}", "catalog:read"),
    ("structured", "/agent/semantic/dimensions/{dimension_id}/history", "catalog:read"),
    ("structured", "/agent/semantic/metrics", "catalog:read"),
    ("structured", "/agent/semantic/metrics/{metric_id}", "catalog:read"),
    ("structured", "/agent/semantic/metrics/{metric_id}/history", "catalog:read"),
    ("structured", "/agent/tables", "catalog:read"),
    ("structured", "/agent/tables/by-name/{name}", "catalog:read"),
    ("structured", "/agent/tables/{table_id}", "catalog:read"),
    ("structured", "/agent/tables/{table_id}/changes", "catalog:read"),
    ("structured", "/agent/tables/{table_id}/objects", "catalog:read"),
    ("structured", "/agent/tables/{table_id}/snapshots", "catalog:read"),
    ("structured", "/agent/version", "catalog:read"),
    ("structured", "/audit-events", "audit:read"),
    ("structured", "/billing", "audit:read"),
    ("structured", "/conversations", "catalog:read"),
    ("structured", "/conversations/{conversation_id}", "catalog:read"),
    ("structured", "/cost-events", "audit:read"),
    ("structured", "/datasets", "catalog:read"),
    ("structured", "/datasets/by-name/{name}", "catalog:read"),
    ("structured", "/datasets/{dataset_id}", "catalog:read"),
    ("structured", "/datasets/{dataset_id}/relations", "catalog:read"),
    ("structured", "/datasets/{dataset_id}/tables", "catalog:read"),
    ("structured", "/examples", "catalog:read"),
    ("structured", "/examples/{example_id}", "catalog:read"),
    ("structured", "/glossary", "catalog:read"),
    ("structured", "/glossary/{term_id}", "catalog:read"),
    ("structured", "/ingest-jobs", "catalog:read"),
    ("structured", "/ingest-jobs/{job_id}", "catalog:read"),
    ("structured", "/ingest-jobs/{job_id}/callbacks", "catalog:read"),
    ("structured", "/ingest-jobs/{job_id}/events", "catalog:read"),
    ("structured", "/ingest-jobs/{job_id}/stream", "catalog:read"),
    ("structured", "/queries", "catalog:read"),
    ("structured", "/queries/{query_id}", "catalog:read"),
    ("structured", "/queries/{query_id}/result", "catalog:read"),
    ("structured", "/schema-objects/{object_id}", "catalog:read"),
    ("structured", "/semantic/dimensions", "catalog:read"),
    ("structured", "/semantic/dimensions/{dimension_id}", "catalog:read"),
    ("structured", "/semantic/dimensions/{dimension_id}/history", "catalog:read"),
    ("structured", "/semantic/metrics", "catalog:read"),
    ("structured", "/semantic/metrics/{metric_id}", "catalog:read"),
    ("structured", "/semantic/metrics/{metric_id}/history", "catalog:read"),
    ("structured", "/stats", "catalog:read"),
    ("structured", "/tables", "catalog:read"),
    ("structured", "/tables/by-name/{name}", "catalog:read"),
    ("structured", "/tables/{table_id}", "catalog:read"),
    ("structured", "/tables/{table_id}/changes", "catalog:read"),
    ("structured", "/tables/{table_id}/objects", "catalog:read"),
    ("structured", "/tables/{table_id}/snapshots", "catalog:read"),
    ("structured", "/version", "catalog:read"),
)

READ_AGENT_SCOPES = {
    ("canon", "/agent/knowledge/{item_id}"): ("agent.knowledge:read",),
    ("canon", "/agent/knowledge/{item_id}/provenance"): ("agent.knowledge:read",),
    ("canon", "/agent/sources/{source_id}"): ("agent.sources:read",),
    ("structured", "/agent/conversations"): ("flyquery.conversations:read",),
    ("structured", "/agent/conversations/{conversation_id}"): ("flyquery.conversations:read",),
    ("structured", "/agent/datasets"): ("flyquery.datasets:read",),
    ("structured", "/agent/datasets/by-name/{name}"): ("flyquery.datasets:read",),
    ("structured", "/agent/datasets/{dataset_id}"): ("flyquery.datasets:read",),
    ("structured", "/agent/datasets/{dataset_id}/relations"): ("flyquery.relations:read",),
    ("structured", "/agent/datasets/{dataset_id}/tables"): ("flyquery.schema:read",),
    ("structured", "/agent/examples"): ("flyquery.examples:read",),
    ("structured", "/agent/glossary"): ("flyquery.semantic:read",),
    ("structured", "/agent/glossary/{term_id}"): ("flyquery.semantic:read",),
    ("structured", "/agent/ingest-jobs"): ("flyquery.ingest:read",),
    ("structured", "/agent/ingest-jobs/{job_id}"): ("flyquery.ingest:read",),
    ("structured", "/agent/ingest-jobs/{job_id}/events"): ("flyquery.ingest:read",),
    ("structured", "/agent/ingest-jobs/{job_id}/stream"): ("flyquery.ingest:read",),
    ("structured", "/agent/schema-objects/{object_id}"): ("flyquery.schema:read",),
    ("structured", "/agent/semantic/dimensions"): ("flyquery.semantic:read",),
    ("structured", "/agent/semantic/dimensions/{dimension_id}"): ("flyquery.semantic:read",),
    ("structured", "/agent/semantic/dimensions/{dimension_id}/history"): ("flyquery.semantic:read",),
    ("structured", "/agent/semantic/metrics"): ("flyquery.semantic:read",),
    ("structured", "/agent/semantic/metrics/{metric_id}"): ("flyquery.semantic:read",),
    ("structured", "/agent/semantic/metrics/{metric_id}/history"): ("flyquery.semantic:read",),
    ("structured", "/agent/tables"): ("flyquery.schema:read",),
    ("structured", "/agent/tables/by-name/{name}"): ("flyquery.schema:read",),
    ("structured", "/agent/tables/{table_id}"): ("flyquery.schema:read",),
    ("structured", "/agent/tables/{table_id}/changes"): ("flyquery.schema:read",),
    ("structured", "/agent/tables/{table_id}/objects"): ("flyquery.schema:read",),
    ("structured", "/agent/tables/{table_id}/snapshots"): ("flyquery.schema:read",),
}

TABLES = {
    "canon": {
        "source": "canon_sources",
        "candidate": "canon_candidates",
        "item": "canon_knowledge_items",
        "conversation": "canon_conversations",
        "job": "canon_ingest_jobs",
    },
    "structured": {
        "dataset": "flyquery_datasets",
        "table": "flyquery_tables",
        "object": "flyquery_schema_objects",
        "snapshot": "flyquery_schema_snapshots",
        "query": "flyquery_queries",
        "conversation": "flyquery_conversations",
        "job": "flyquery_ingest_jobs",
        "term": "flyquery_glossary_terms",
        "metric": "flyquery_semantic_metrics",
        "dimension": "flyquery_semantic_dimensions",
        "example": "flyquery_examples",
    },
}
PARAMETERS = {
    "source_id": "source",
    "candidate_id": "candidate",
    "item_id": "item",
    "dataset_id": "dataset",
    "table_id": "table",
    "object_id": "object",
    "snapshot_id": "snapshot",
    "query_id": "query",
    "conversation_id": "conversation",
    "job_id": "job",
    "term_id": "term",
    "metric_id": "metric",
    "dimension_id": "dimension",
    "example_id": "example",
}
PARENTS = {
    "canon": {"candidate": (("source_id", "source"),)},
    "structured": {
        "table": (("dataset_id", "dataset"),),
        "object": (("table_id", "table"), ("snapshot_id", "snapshot")),
        "snapshot": (("table_id", "table"), ("dataset_id", "dataset")),
        "query": (("dataset_id", "dataset"),),
        "job": (("dataset_id", "dataset"), ("table_id", "table")),
        "metric": (("dataset_id", "dataset"),),
        "dimension": (("dataset_id", "dataset"),),
        "example": (("dataset_id", "dataset"),),
    },
}


@component(name="knowledge.legacy_read_admission")
class LegacyReadAdmission:
    def __init__(
        self,
        knowledge: KnowledgeFacade,
        datasources: DataSourceRegistry,
        policies: LegacyOperationPolicies,
        capabilities: CapabilityRegistry,
        query_reads: NativeQueryRepository | None = None,
    ):
        self.knowledge, self.datasources = knowledge, datasources
        self.query_reads = query_reads
        for domain, path, permission in READ_OPERATIONS:
            if capabilities.domains.get(domain, {}).get("registered"):
                policies.register(
                    domain,
                    "GET",
                    path,
                    self._verifier(domain),
                    permission,
                    agent_scopes=READ_AGENT_SCOPES.get((domain, path), ()),
                )

    def _verifier(self, domain):
        async def verify(request, identity, tenant, workspace, parameters):
            await self.verify(domain, request, identity, tenant, workspace, parameters)

        return verify

    async def _lookup(self, domain, kind, identifier, tenant, workspace):
        if kind not in TABLES[domain]:
            raise AccessDenied("Unknown retained resource kind", code="LEGACY_SCOPE_DENIED")
        try:
            identifier = UUID(identifier) if domain == "structured" else identifier
            native_workspace = UUID(workspace) if domain == "structured" else workspace
        except (ValueError, TypeError, AttributeError) as error:
            raise AccessDenied(
                "Resource is outside the admitted scope", code="LEGACY_SCOPE_DENIED"
            ) from error
        if domain == "structured" and kind == "query":
            if self.query_reads is None:
                raise ServiceUnavailableException(
                    "Retained query admission is unavailable", code="LEGACY_QUERY_AUTHORITY_REQUIRED"
                )
            return await self.query_reads.legacy_query_metadata(identifier, tenant, native_workspace)
        table = TABLES[domain][kind]
        columns = {"id", "tenant_id", "workspace_id"} | {
            column for column, _ in PARENTS[domain].get(kind, ())
        }
        async with infrastructure_unit(self.datasources.get(domain)) as session:
            result = await session.execute(
                text(
                    f"SELECT {', '.join(sorted(columns))} FROM {table} "
                    "WHERE id = :id AND tenant_id = :tenant AND workspace_id = :workspace"
                ),
                {"id": identifier, "tenant": tenant, "workspace": native_workspace},
            )
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def verify(self, domain, request, identity, tenant, workspace, parameters):
        await self.knowledge._chain(identity.subject, tenant, workspace)
        restriction = self.knowledge.catalog.restriction
        grant = await restriction.grant(identity.subject) if restriction else None
        asset_restricted = grant is not None and grant.asset_ids is not None
        if asset_restricted and not any(name in PARAMETERS for name in parameters):
            raise AccessDenied(
                "This retained operation cannot project the API token asset scope", code="TOKEN_SCOPE_DENIED"
            )
        workspace_bindings = await self.knowledge.bindings.find_all(
            tenant_id=tenant, catalog_id=workspace, domain=domain
        )
        native_workspace = workspace_bindings[0].native_workspace_id if workspace_bindings else workspace
        values = dict(parameters)
        for name, value in request.query_params.multi_items():
            if name in PARAMETERS:
                if name in values and values[name] != value:
                    raise AccessDenied("Conflicting retained resource context", code="LEGACY_SCOPE_DENIED")
                values[name] = value
            if (name == "tenant_id" and value != tenant) or (name == "workspace_id" and value != workspace):
                raise AccessDenied(
                    "Query scope disagrees with the selected context", code="LEGACY_SCOPE_DENIED"
                )
        visited = {}
        if domain == "structured" and not any(name in PARAMETERS for name in parameters):
            datasets = await self.knowledge.catalog.catalog_repository.find_all(
                tenant_id=tenant, workspace_id=workspace, kind="dataset"
            )
            for dataset in datasets:
                self.knowledge._ready_dataset(dataset)

        async def admit(kind, identifier):
            key = kind, str(identifier)
            if key in visited:
                return visited[key]
            if len(visited) >= 32:
                raise AccessDenied("Retained resource ancestry is too deep", code="LEGACY_SCOPE_DENIED")
            visited[key] = False
            bindings = await self.knowledge.bindings.find_all(
                tenant_id=tenant,
                domain=domain,
                native_id=str(identifier),
                native_workspace_id=native_workspace,
            )
            rejection, covered = None, False
            for binding in bindings:
                try:
                    chain = await self.knowledge._chain(identity.subject, tenant, binding.catalog_id)
                    entry = chain[0]
                    if domain == "structured":
                        for ancestor in chain:
                            if ancestor.kind == "dataset":
                                self.knowledge._ready_dataset(ancestor)
                    if entry.workspace_id != workspace or binding.workspace_id != workspace:
                        raise AccessDenied(
                            "Catalog binding disagrees with retained context", code="LEGACY_SCOPE_DENIED"
                        )
                    covered = True
                    break
                except AccessDenied as error:
                    rejection = error
            else:
                if bindings and rejection is not None:
                    raise rejection
            row = await self._lookup(domain, kind, str(identifier), tenant, native_workspace)
            if row is None or row["tenant_id"] != tenant or str(row["workspace_id"]) != native_workspace:
                raise AccessDenied("Resource is outside the admitted scope", code="LEGACY_SCOPE_DENIED")
            for name, expected in values.items():
                if name in row and row[name] is not None and str(row[name]) != expected:
                    raise AccessDenied(
                        "Retained child disagrees with its selected ancestor", code="LEGACY_SCOPE_DENIED"
                    )
            for column, parent_kind in PARENTS[domain].get(kind, ()):
                if row.get(column) is not None:
                    covered = await admit(parent_kind, row[column]) or covered
            visited[key] = covered
            return covered

        with native_scope(domain, tenant, native_workspace, identity.subject):
            for name, identifier in values.items():
                if name in PARAMETERS:
                    covered = await admit(PARAMETERS[name], identifier)
                    if asset_restricted and not covered:
                        raise AccessDenied(
                            "Retained resource has no authorized catalog asset binding",
                            code="TOKEN_SCOPE_DENIED",
                        )
        request.state.verified_native_workspace_id = native_workspace

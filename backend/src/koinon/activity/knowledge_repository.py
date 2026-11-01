# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded content-free projections of committed business and source receipts."""

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import JSON, String, case, cast, column, exists, func, literal, or_, select
from sqlalchemy.sql import Select

from koinon.activity.dtos import ActivityWindow
from koinon.activity.knowledge_values import ActivityCatalogNode, KnowledgeObservation
from koinon.assistants.entities import ChatRun, ChatThread, ToolResult
from koinon.catalog.entities import AuditEvent, CatalogEntry
from koinon.knowledge.external_reviews.read_receipt_entities import ExternalReadReceiptRow

HISTORY_LIMIT = 10000
PIECE_KINDS = ("document", "dataset", "knowledge_item")


@repository
class KnowledgeActivityRepository(Repository[AuditEvent, str]):
    async def node(self, tenant_id: str, asset_id: str) -> ActivityCatalogNode | None:
        row = (
            await self._require_session().execute(
                select(
                    CatalogEntry.id,
                    CatalogEntry.tenant_id,
                    CatalogEntry.parent_id,
                    CatalogEntry.workspace_id,
                    CatalogEntry.project_id,
                    CatalogEntry.kind,
                    CatalogEntry.status,
                    CatalogEntry.name,
                    CatalogEntry.updated_at,
                ).where(CatalogEntry.tenant_id == tenant_id, CatalogEntry.id == asset_id)
            )
        ).one_or_none()
        return ActivityCatalogNode(*row) if row is not None else None

    async def observations(
        self, tenant_id: str, subject: str | None, window: ActivityWindow
    ) -> tuple[list[KnowledgeObservation], bool]:
        audit = (
            select(
                AuditEvent.resource_id.label("asset_id"),
                case(
                    (
                        AuditEvent.action.in_(
                            ("catalog.created", "knowledge.create_draft", "knowledge.create_published")
                        ),
                        "created",
                    ),
                    else_="updated",
                ).label("action"),
                AuditEvent.created_at.label("occurred_at"),
            )
            .join(CatalogEntry, CatalogEntry.id == AuditEvent.resource_id)
            .where(
                AuditEvent.tenant_id == tenant_id,
                CatalogEntry.tenant_id == tenant_id,
                CatalogEntry.kind.in_(PIECE_KINDS),
                AuditEvent.action.in_(
                    (
                        "catalog.created",
                        "catalog.updated",
                        "knowledge.create_draft",
                        "knowledge.create_published",
                        "knowledge.update_draft",
                        "knowledge.update_published",
                        "knowledge.publish_draft",
                        "knowledge.content_updated",
                    )
                ),
                AuditEvent.created_at >= window.start_at,
                AuditEvent.created_at < window.end_at,
            )
        )
        fields = AuditEvent.details["fields"]
        if self._require_session().get_bind().dialect.name == "postgresql":
            safe = case((func.json_typeof(fields) == "array", fields), else_=cast(literal("[]"), JSON))
            changed = func.json_array_elements_text(safe).table_valued("value").alias("activity_changes")
        else:
            changed = func.json_each(fields).table_valued("value").alias("activity_changes")
        meaningful = exists(
            select(literal(1))
            .select_from(changed)
            .where(changed.c.value.in_(("name", "description", "metadata")))
        ).correlate(AuditEvent)
        audit = audit.where(or_(AuditEvent.action != "catalog.updated", meaningful))
        if subject is not None:
            audit = audit.where(AuditEvent.subject == subject)
        receipt = self._reads(tenant_id, subject, window, chat=False)
        chat = self._reads(tenant_id, subject, window, chat=True)
        statement = audit.union_all(receipt, chat).subquery()
        rows = (
            await self._require_session().execute(
                select(statement.c.asset_id, statement.c.action, statement.c.occurred_at)
                .order_by(statement.c.occurred_at, statement.c.asset_id, statement.c.action)
                .limit(HISTORY_LIMIT + 1)
            )
        ).all()
        return (
            [
                KnowledgeObservation(str(row.asset_id), row.action, row.occurred_at)
                for row in rows[:HISTORY_LIMIT]
            ],
            len(rows) > HISTORY_LIMIT,
        )

    def _reads(self, tenant_id: str, subject: str | None, window: ActivityWindow, *, chat: bool) -> Select:
        if chat:
            sources = ToolResult.payload["source_manifest"]["sources"]
            clock = ToolResult.created_at
            predicates = [
                ChatRun.tenant_id == tenant_id,
                ChatThread.tenant_id == tenant_id,
                ToolResult.kind.in_(("search", "query")),
                ToolResult.payload["source_manifest"]["complete"].as_boolean().is_(True),
                ChatThread.deleted_at.is_(None),
            ]
            if subject is not None:
                predicates.append(ChatThread.subject == subject)
        else:
            sources, clock = ExternalReadReceiptRow.sources_json, ExternalReadReceiptRow.created_at
            predicates = [
                ExternalReadReceiptRow.tenant_id == tenant_id,
                ExternalReadReceiptRow.operation.in_(("search", "query", "fetch")),
            ]
            if subject is not None:
                predicates.append(ExternalReadReceiptRow.subject == subject)
        dialect = self._require_session().get_bind().dialect.name
        if dialect == "postgresql":
            elements = (
                func.json_array_elements(sources)
                .table_valued(column("value", JSON))
                .alias("activity_sources")
            )
            asset = elements.c.value["asset_id"].as_string()
        else:
            elements = func.json_each(sources).table_valued("value").alias("activity_sources")
            asset = func.json_extract(elements.c.value, "$.asset_id", type_=String)
        statement = select(
            asset.label("asset_id"), literal("consulted").label("action"), clock.label("occurred_at")
        )
        if chat:
            statement = (
                statement.select_from(ToolResult)
                .join(ChatRun, ChatRun.id == ToolResult.run_id)
                .join(ChatThread, ChatThread.id == ChatRun.thread_id)
            )
        else:
            statement = statement.select_from(ExternalReadReceiptRow)
        return statement.join(elements, literal(True)).where(
            *predicates, clock >= window.start_at, clock < window.end_at, asset.is_not(None)
        )

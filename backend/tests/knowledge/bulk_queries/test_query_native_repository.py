# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import JSON, Column, MetaData, Table, select
from sqlalchemy.dialects.postgresql import ARRAY, JSONB


def policy():
    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings

    from koinon.organization_knowledge.dtos import (
        DocumentKnowledgeSettings,
        OrganizationKnowledgeSnapshot,
        StructuredKnowledgeSettings,
        snapshot_digest,
    )

    documents, structured = CanonSettings(), FlyquerySettings()
    doc = {
        name: getattr(documents, name)
        for name in DocumentKnowledgeSettings.model_fields
        if name not in {"answer_top_k", "rlm_extended_reasoning"}
    }
    values = {
        "tenant_id": "north",
        "schema_version": 1,
        "revision": 0,
        "origin": "deployment",
        "documents": {**doc, "answer_top_k": 10, "rlm_extended_reasoning": False},
        "structured": {name: getattr(structured, name) for name in StructuredKnowledgeSettings.model_fields},
    }
    return OrganizationKnowledgeSnapshot.model_validate({**values, "digest": snapshot_digest(values)})


@pytest.fixture
async def native_queries(tmp_path):
    from flyquery.models.entities.dataset import Dataset
    from flyquery.models.entities.queries import Query
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
    from koinon.knowledge.bulk_queries.native_entities import NativeQueryOperation
    from koinon.knowledge.bulk_queries.native_repository import NativeQueryRepository

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {
                                "structured": {
                                    "url": f"sqlite+aiosqlite:///{tmp_path / 'structured.db'}",
                                    "ddl-auto": "none",
                                }
                            },
                        }
                    }
                }
            }
        )
    )
    context.register_bean(StructuredBulkRepository)
    context.register_bean(NativeQueryRepository)
    await context.start()
    try:
        native = context.get_bean(DataSourceRegistry).get("structured")
        metadata = MetaData()
        for entity in [Dataset, Query]:
            Table(
                entity.__tablename__,
                metadata,
                *[
                    Column(
                        c.name,
                        JSON() if isinstance(c.type, (JSONB, ARRAY)) else c.type,
                        primary_key=c.primary_key,
                        nullable=c.nullable,
                    )
                    for c in entity.__table__.columns
                ],
            )
        async with native.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.run_sync(NativeQueryOperation.__table__.create)
        repository = context.get_bean(NativeQueryRepository)
        repository.resources = SimpleNamespace(native=lambda: native)
        yield repository, metadata
    finally:
        await context.stop()


def values(table, **changes):
    result = {}
    for column in table.columns:
        if column.name in changes:
            result[column.name] = changes[column.name]
        elif column.nullable:
            result[column.name] = None
        elif isinstance(column.type, JSON):
            result[column.name] = [] if column.name in {"prior_turn_ids", "candidates_json"} else {}
        else:
            kind = column.type.python_type
            result[column.name] = (
                {
                    str: "seed",
                    UUID: uuid4(),
                    int: 0,
                    bool: False,
                    float: 0.0,
                    datetime: datetime.now(UTC),
                    Decimal: Decimal(0),
                }
            )[kind]
    return result


async def test_native_query_and_receipt_commit_atomically_and_rollback_never_becomes_success(native_queries):
    from pyfly.kernel import ConflictException

    from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
    from koinon.knowledge.bulk_queries.native_repository import receipt_of
    from koinon.knowledge.bulk_queries.native_values import QueryOperationIdentity

    repository, metadata = native_queries
    selected = policy()
    identity = QueryOperationIdentity(
        operation_id=uuid4(),
        tenant_id="north",
        subject="owner",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        catalog_workspace_id="workspace",
        catalog_dataset_id="dataset",
        question="Count",
        policy_sha256=selected.digest,
        connections_sha256="a" * 64,
    )
    async with repository.write() as unit:
        await unit.session.execute(
            metadata.tables["flyquery_datasets"].insert(),
            values(
                metadata.tables["flyquery_datasets"],
                id=identity.dataset_id,
                tenant_id="north",
                workspace_id=identity.workspace_id,
                status="ACTIVE",
            ),
        )
        await unit.admit(identity)
    query_id = uuid4()
    outcome = BatchQueryOutcome(
        query_id=query_id,
        execution_status="OK",
        sql="SELECT 1",
        preview=[{"value": 1}],
        row_count=1,
        elapsed_ms=1,
        knowledge_settings_snapshot=selected,
    )

    async def commit(unit):
        await unit.session.execute(
            metadata.tables["flyquery_queries"].insert(),
            values(
                metadata.tables["flyquery_queries"],
                id=query_id,
                tenant_id="north",
                workspace_id=identity.workspace_id,
                dataset_id=identity.dataset_id,
                question="Count",
                executed_sql="SELECT 1",
                execution_status="OK",
                row_count=1,
                elapsed_ms=1,
            ),
        )
        return await unit.commit(identity, outcome)

    with pytest.raises(ConflictException):
        async with repository.write() as unit:
            await unit.session.execute(
                metadata.tables["flyquery_datasets"]
                .update()
                .where(metadata.tables["flyquery_datasets"].c.id == identity.dataset_id)
                .values(status="ARCHIVED")
            )
            await commit(unit)
    with pytest.raises(TimeoutError):
        async with repository.write() as unit:
            await commit(unit)
            raise TimeoutError("Simulated cancellation before native transaction commit")
    async with repository.read() as unit:
        row = await unit.row(identity)
        assert row.status == "admitted" and receipt_of(row) is None
        assert await unit.session.scalar(select(metadata.tables["flyquery_queries"].c.id)) is None
        assert await unit.row(identity.model_copy(update={"subject": "foreign"})) is None
    async with repository.write() as unit:
        receipt = await commit(unit)
    async with repository.read() as unit:
        assert receipt_of(await unit.row(identity)) == receipt
    assert await repository.legacy_query_metadata(query_id, "north", identity.workspace_id) is None
    unmarked = uuid4()
    async with repository.write() as unit:
        await unit.session.execute(
            metadata.tables["flyquery_queries"].insert(),
            values(
                metadata.tables["flyquery_queries"],
                id=unmarked,
                tenant_id="north",
                workspace_id=identity.workspace_id,
                dataset_id=identity.dataset_id,
            ),
        )
    metadata_row = await repository.legacy_query_metadata(unmarked, "north", identity.workspace_id)
    assert metadata_row == {
        "id": unmarked,
        "tenant_id": "north",
        "workspace_id": identity.workspace_id,
        "dataset_id": identity.dataset_id,
    }
    assert await repository.legacy_query_metadata(unmarked, "foreign", identity.workspace_id) is None
    async with repository.write() as unit:
        assert await unit.commit(identity, outcome) == receipt
        with pytest.raises(ConflictException):
            await unit.commit(identity, outcome.model_copy(update={"sql": "SELECT 2"}))

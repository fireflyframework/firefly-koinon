# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Receipt projections run against PostgreSQL JSON operators, never protected payloads."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_source_migration_postgres import source_database as source_database

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("identity_kind", ["ordinary", "source"])
async def test_structured_receipt_projection_reads_bounded_safe_json_fields_on_postgres(
    source_database, identity_kind
):
    from flyquery.models.entities.dataset import Dataset
    from flyquery.models.entities.workspace import Workspace

    from koinon.knowledge.bulk.structured_dtos import StructuredOperationIdentity
    from koinon.knowledge.bulk.structured_entities import StructuredBulkOperation
    from koinon.knowledge.bulk.structured_repository import StructuredBulkUnit

    target, _, engine = source_database
    for entity in (Workspace, Dataset, StructuredBulkOperation):
        entity.__table__.create(engine)
    identity = StructuredOperationIdentity(
        operation_id=uuid4(),
        tenant_id="tenant",
        workspace_id=uuid4(),
        dataset_id=uuid4(),
        file_id=uuid4(),
        actor="owner",
        catalog_source_id="source",
        catalog_dataset_id="asset",
        catalog_file_version_id="version",
        filename="protected-filename.csv",
        sha256="a" * 64,
        size_bytes=7,
    )
    table_id, snapshot_id = uuid4(), uuid4()
    receipt = dict(
        file_id=str(identity.file_id),
        dataset_id=str(identity.dataset_id),
        sha256=identity.sha256,
        size_bytes=7,
        object_key="opaque-key",
        source_attempt_id="source-attempt" if identity_kind == "source" else None,
        source_publication_sha256="b" * 64 if identity_kind == "source" else None,
        tables=[
            dict(
                ordinal=0,
                catalog_table_id="table",
                table_id=str(table_id),
                snapshot_id=str(snapshot_id),
                n_columns=2,
                n_rows_actual=3,
                name="never hydrate this name",
            )
        ],
    )
    with engine.begin() as connection:
        connection.execute(
            Workspace.__table__.insert(),
            dict(id=identity.workspace_id, tenant_id="tenant", slug="fixture", name="private"),
        )
        connection.execute(
            Dataset.__table__.insert(),
            dict(
                id=identity.dataset_id, tenant_id="tenant", workspace_id=identity.workspace_id, name="private"
            ),
        )
        values = identity.model_dump(mode="python")
        values["id"] = values.pop("operation_id")
        connection.execute(
            StructuredBulkOperation.__table__.insert(),
            dict(
                **values,
                status="committed",
                plan_json=[{"private": "plan"}],
                prepared_json=[{"private": "schema"}],
                receipt_json=receipt,
                source_attempt_id=receipt["source_attempt_id"],
                source_publication_sha256=receipt["source_publication_sha256"],
                created_at=datetime.now(UTC),
            ),
        )
    async_engine = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    if identity_kind == "source":
        from koinon.knowledge.bulk.structured_repository import SourceStructuredReceiptIdentity

        lookup = SourceStructuredReceiptIdentity(
            **identity.model_dump(exclude={"filename"}),
            source_attempt_id=receipt["source_attempt_id"],
            source_publication_sha256=receipt["source_publication_sha256"],
        )
    else:
        lookup = identity

    async def inspect(session, selected=lookup):
        unit = StructuredBulkUnit(session)
        if identity_kind == "source":
            return await unit.inspect_source_receipt(selected)
        return await unit.inspect_receipt(selected)

    try:
        from sqlalchemy import event

        statements = []

        @event.listens_for(async_engine.sync_engine, "before_cursor_execute")
        def captured(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        async with async_sessionmaker(async_engine)() as session:
            observed = await inspect(session)
            assert observed.status == "committed"
            assert observed.receipt.tables[0].table_id == str(table_id)
            assert observed.receipt.tables[0].n_columns == 2
            assert "never hydrate" not in repr(observed) and "protected-filename" not in repr(observed)
        if identity_kind == "source":
            assert statements and all(
                forbidden not in statement.lower()
                for statement in statements
                for forbidden in ("filename", "plan_json", "prepared_json", "baseline_json")
            )
            from dataclasses import replace

            from pyfly.kernel import ConflictException

            for field, value in (
                ("source_attempt_id", "substituted"),
                ("source_publication_sha256", "c" * 64),
                ("catalog_source_id", "foreign-source"),
                ("catalog_dataset_id", "foreign-asset"),
                ("catalog_file_version_id", "foreign-index"),
                ("file_id", uuid4()),
            ):
                async with async_sessionmaker(async_engine)() as session:
                    with pytest.raises(ConflictException):
                        await inspect(session, replace(lookup, **{field: value}))
        from pyfly.kernel import ConflictException

        for invalid in (
            {**receipt, "tables": receipt["tables"] * 17},
            {**receipt, "sha256": "b" * 64},
            {**receipt, "tables": [{**receipt["tables"][0], "snapshot_id": "not-a-uuid"}]},
        ):
            with engine.begin() as connection:
                connection.execute(
                    StructuredBulkOperation.__table__.update()
                    .where(StructuredBulkOperation.id == identity.operation_id)
                    .values(receipt_json=invalid)
                )
            async with async_sessionmaker(async_engine)() as session:
                with pytest.raises(ConflictException):
                    await inspect(session)
    finally:
        await async_engine.dispose()


async def test_canon_receipt_projection_extracts_count_without_filename_on_postgres(source_database):
    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.core.services.sources.lineage.ports import LineageQuery
    from flycanon.models.entities.source_lineage import (
        metadata,
        source_artifacts,
        source_extractions,
        source_versions,
    )
    from flycanon.models.repositories.lineage.repository import NativeLineageUnit

    target, _, engine = source_database
    metadata.create_all(engine)
    scope = dict(tenant_id="tenant", workspace_id="workspace", source_id="source")
    with engine.begin() as connection:
        connection.execute(
            source_artifacts.insert(),
            dict(id="artifact", **scope, role="original", sha256="a" * 64, bytes=7, object_key="opaque"),
        )
        connection.execute(
            source_versions.insert(),
            dict(
                id="version",
                **scope,
                artifact_id="artifact",
                logical_key="logical",
                operation_id="operation",
                filename="private",
            ),
        )
        connection.execute(
            source_extractions.insert(),
            dict(
                id="extraction",
                **scope,
                version_id="version",
                purpose="ingestion",
                normalized_artifact_id="artifact",
                implementation={},
                coverage="section",
                projection={"filename": "private", "n_chunks": 5},
            ),
        )
    async_engine = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    try:
        async with async_sessionmaker(async_engine)() as session:
            row = await NativeLineageUnit(session).one(
                LineageQuery(
                    "extraction", DocumentScope("tenant", "workspace", "actor"), projection="intake_receipt"
                )
            )
            assert row == {"id": "extraction", "source_id": "source", "version_id": "version", "n_chunks": 5}
    finally:
        await async_engine.dispose()

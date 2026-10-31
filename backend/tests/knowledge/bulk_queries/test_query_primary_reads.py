# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private stored query output intersects current primary membership and token grants."""

import sqlite3
from datetime import timedelta
from uuid import uuid4

import pytest
from pyfly.data.relational.datasource_registry import DataSource, DataSourceRegistry
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_query_native_repository import policy
from test_query_service import request

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
from koinon.knowledge.bulk_queries.entities import QueryBatchItem
from koinon.knowledge.bulk_queries.service import QueryBatches
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


@pytest.mark.parametrize("operation", ["get", "items", "result", "list", "capabilities"])
@pytest.mark.parametrize("revocation", ["membership", "token"])
async def test_query_guards_never_release_replica_authorized_results(
    queries, tmp_path, operation, revocation
):
    token = PersonalToken(
        id="query-read-origin",
        subject="issuer|analyst",
        tenant_id="north",
        name="Inert",
        token_hash="a" * 64,
        prefix="test",
        scopes=["catalog:read", "query:execute"],
        workspace_ids=[queries.workspace.id],
        asset_ids=None,
        resource_ids=None,
        expires_at=now() + timedelta(hours=1),
    )
    await queries.context.get_bean(PersonalTokenRepository).save(token)
    service = queries.context.get_bean(QueryBatches)
    with SecurityContextHolder.using(
        SecurityContext(user_id=token.subject, attributes={"koinon_token_id": token.id})
    ):
        batch = await service.create(token.subject, "north", request(queries), "replica-query")
        item = (await service.items(token.subject, "north", batch.id)).items[0]
        registry = queries.context.get_bean(DataSourceRegistry)
        primary = registry.get("primary")
        result = BatchQueryOutcome(
            query_id=uuid4(),
            execution_status="OK",
            sql="SELECT 'CURRENTLY_FORBIDDEN_SOURCE_BODY' AS private_value",
            preview=[{"private_value": "CURRENTLY_FORBIDDEN_SOURCE_BODY"}],
            knowledge_settings_snapshot=policy(),
        )
        async with primary.engine.begin() as connection:
            await connection.execute(
                update(QueryBatchItem)
                .where(QueryBatchItem.id == item.id)
                .values(status="succeeded", result_json=result.model_dump(mode="json"))
            )
        replica_path = tmp_path / "lagging-query-policy.db"
        with (
            sqlite3.connect(primary.engine.url.database) as original,
            sqlite3.connect(replica_path) as backup,
        ):
            original.backup(backup)
        replica_engine = create_async_engine("sqlite+aiosqlite:///" + str(replica_path))
        primary.replica = DataSource(
            "primary",
            replica_engine,
            async_sessionmaker(replica_engine),
            properties=primary.properties,
            registry=registry,
            is_replica=True,
        )
        try:
            async with primary.engine.begin() as connection:
                if revocation == "membership":
                    await connection.execute(
                        update(Membership).where(Membership.id == token.subject).values(active=False)
                    )
                else:
                    await connection.execute(
                        update(PersonalToken)
                        .where(PersonalToken.id == token.id)
                        .values(scopes=["catalog:read"])
                    )
            arguments = (token.subject, "north")
            if operation == "capabilities":
                arguments += (queries.workspace.id,)
            elif operation != "list":
                arguments += (batch.id,)
            if operation == "result":
                arguments += (item.id,)
            with pytest.raises(AccessDenied):
                await getattr(service, operation)(*arguments)
        finally:
            primary.replica = None
            await replica_engine.dispose()

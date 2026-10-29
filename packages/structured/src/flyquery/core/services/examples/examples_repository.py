# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Async SQLAlchemy repository for flyquery_examples."""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa
from pyfly.container import repository
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy.exc import NoResultFound

from flyquery.data import StructuredSessions, unwrap_sessions


@repository(name="structured.ExamplesRepository")
class ExamplesRepository:
    """Repository over ``flyquery_examples``.

    Every operation owns its own session + transaction lifetime via
    the injected ``async_sessionmaker``.
    """

    def __init__(self, session: StructuredSessions) -> None:
        self._factory = unwrap_sessions(session)

    async def create(self, **fields: Any) -> dict[str, Any]:
        """Insert a new examples row and return the full record."""
        if "citations_json" in fields and isinstance(fields["citations_json"], dict):
            fields = {**fields, "citations_json": json.dumps(fields["citations_json"])}
        embedding = fields.pop("embedding", None)
        from flyquery.core.agents.model_bindings import embedding_for

        binding = embedding_for("structured.embedding")
        versioned = binding is not None and binding.versioned
        async with infrastructure_unit(self._factory) as s:
            from flyquery.core.services.retrieval.index_scope import guard_publication

            await guard_publication(s, binding)
            if embedding is not None and not versioned:
                result = await s.execute(
                    sa.text(
                        """
                        INSERT INTO flyquery_examples
                            (tenant_id, workspace_id, dataset_id, question, generated_sql,
                             normalised_sql, source, quality, citations_json, created_by, embedding)
                        VALUES
                            (:tenant_id, :workspace_id, :dataset_id, :question, :generated_sql,
                             :normalised_sql, :source, :quality,
                             CAST(:citations_json AS jsonb), :created_by,
                             CAST(:embedding AS vector))
                        RETURNING id, tenant_id, workspace_id, dataset_id, question,
                                  generated_sql, normalised_sql, source, quality,
                                  citations_json, created_at, created_by, last_used_at, usage_count
                        """
                    ),
                    {**fields, "embedding": str(embedding)},
                )
            else:
                result = await s.execute(
                    sa.text(
                        """
                        INSERT INTO flyquery_examples
                            (tenant_id, workspace_id, dataset_id, question, generated_sql,
                             normalised_sql, source, quality, citations_json, created_by)
                        VALUES
                            (:tenant_id, :workspace_id, :dataset_id, :question, :generated_sql,
                             :normalised_sql, :source, :quality,
                             CAST(:citations_json AS jsonb), :created_by)
                        RETURNING id, tenant_id, workspace_id, dataset_id, question,
                                  generated_sql, normalised_sql, source, quality,
                                  citations_json, created_at, created_by, last_used_at, usage_count
                        """
                    ),
                    fields,
                )
            row = result.mappings().one()
            if versioned and embedding is not None:
                from flyquery.core.services.retrieval.sidecar_writer import write_active_vector

                await write_active_vector(
                    self._factory,
                    tenant_id=fields["tenant_id"],
                    object_id=row["id"],
                    kind="example",
                    vector=embedding,
                )
            return dict(row)

    async def list(
        self,
        tenant_id: str,
        workspace_id: uuid.UUID,
        *,
        quality: str | None = None,
        dataset_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Return examples for a workspace, optionally filtered."""
        filters = ["tenant_id = :tenant_id", "workspace_id = :workspace_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "workspace_id": workspace_id, "lim": limit}
        if quality is not None:
            filters.append("quality = :quality")
            params["quality"] = quality
        if dataset_id is not None:
            filters.append("dataset_id = :dataset_id")
            params["dataset_id"] = dataset_id
        where = " AND ".join(filters)
        async with infrastructure_unit(self._factory) as s:
            result = await s.execute(
                sa.text(
                    f"""
                    SELECT id, tenant_id, workspace_id, dataset_id, question,
                           generated_sql, normalised_sql, source, quality,
                           citations_json, created_at, created_by, last_used_at, usage_count
                    FROM flyquery_examples
                    WHERE {where}
                    ORDER BY created_at DESC
                    LIMIT :lim
                    """
                ),
                params,
            )
            return [dict(row) for row in result.mappings().all()]

    async def get(self, example_id: uuid.UUID) -> dict[str, Any] | None:
        """Fetch a single example by primary key."""
        async with infrastructure_unit(self._factory) as s:
            result = await s.execute(
                sa.text(
                    """
                    SELECT id, tenant_id, workspace_id, dataset_id, question,
                           generated_sql, normalised_sql, source, quality,
                           citations_json, created_at, created_by, last_used_at, usage_count
                    FROM flyquery_examples WHERE id = :id
                    """
                ),
                {"id": example_id},
            )
            row = result.mappings().one_or_none()
            return dict(row) if row else None

    async def _review_snapshot(self, example_id: uuid.UUID) -> tuple[dict[str, Any], str]:
        """Capture a private MVCC token without adding it to public example responses."""
        async with infrastructure_unit(self._factory) as session:
            result = await session.execute(
                sa.text(
                    """
                    SELECT id, tenant_id, workspace_id, dataset_id, question,
                           generated_sql, normalised_sql, source, quality,
                           citations_json, created_at, created_by, last_used_at, usage_count,
                           xmin::text AS _review_version
                    FROM flyquery_examples WHERE id = :id
                    """
                ),
                {"id": example_id},
            )
            row = dict(result.mappings().one())
            version = str(row.pop("_review_version"))
            return row, version

    async def update_quality(
        self,
        example_id: uuid.UUID,
        quality: str,
        *,
        embedding: list[float] | None = None,
        expected_source: tuple[str, str] | None = None,
        expected_quality: str | None = None,
        expected_review_version: str | None = None,
    ) -> dict[str, Any]:
        """Change review state; approval and its active vector share the native unit."""
        from flyquery.core.agents.model_bindings import embedding_for

        binding = embedding_for("structured.embedding")
        versioned = binding is not None and binding.versioned
        if quality == "APPROVED" and expected_review_version is None:
            raise ValueError("Example approval requires a private review snapshot")
        if quality == "APPROVED" and versioned and embedding is None:
            raise ValueError("Versioned example approval requires its compatible embedding")
        assignments = "quality = :quality"
        params: dict[str, Any] = {"id": example_id, "quality": quality}
        if embedding is not None and not versioned:
            assignments += ", embedding = CAST(:embedding AS vector)"
            params["embedding"] = str(embedding)
        condition = ""
        if expected_source is not None:
            condition = " AND question=:expected_question AND generated_sql=:expected_sql"
            params.update(expected_question=expected_source[0], expected_sql=expected_source[1])
        if expected_quality is not None:
            condition += " AND quality=:expected_quality"
            params["expected_quality"] = expected_quality
        if expected_review_version is not None:
            condition += " AND xmin::text=:expected_review_version"
            params["expected_review_version"] = expected_review_version
        async with infrastructure_unit(self._factory) as session:
            if quality == "APPROVED":
                from flyquery.core.services.retrieval.index_scope import guard_publication

                await guard_publication(session, binding)
            result = await session.execute(
                sa.text(
                    f"""
                    UPDATE flyquery_examples
                    SET {assignments}
                    WHERE id = :id {condition}
                    RETURNING id, tenant_id, workspace_id, dataset_id, question,
                              generated_sql, normalised_sql, source, quality,
                              citations_json, created_at, created_by, last_used_at, usage_count
                    """
                ),
                params,
            )
            try:
                row = result.mappings().one()
            except NoResultFound:
                if expected_source is None and expected_quality is None and expected_review_version is None:
                    raise
                from pyfly.kernel import ConflictException

                raise ConflictException(
                    "The example source or review state changed; review it again before approval",
                    code="EXAMPLE_REVIEW_CONFLICT",
                ) from None
            if quality == "APPROVED" and versioned:
                from flyquery.core.services.retrieval.sidecar_writer import write_active_vector

                await write_active_vector(
                    self._factory,
                    tenant_id=row["tenant_id"],
                    object_id=row["id"],
                    kind="example",
                    vector=embedding,
                )
            return dict(row)

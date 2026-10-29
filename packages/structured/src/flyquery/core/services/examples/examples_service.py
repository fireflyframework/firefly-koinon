# Copyright 2024-2026 Firefly Software Foundation
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

"""ExamplesService: create, list, approve, reject question+SQL pairs."""

from __future__ import annotations

import re
import uuid
from typing import Any, Protocol

from pyfly.container import service as service_bean

from flyquery.core.services.examples.examples_repository import ExamplesRepository
from flyquery.core.services.retrieval.embedder import Embedder
from flyquery.interfaces.examples import ExampleCreate


def _normalise_sql(sql: str) -> str:
    """Deterministic SQL normalisation for deduplication.

    Tries ``sqlglot`` first (canonical AST round-trip).  Falls back to
    a simple lowercase + whitespace-collapse when sqlglot is unavailable
    or fails to parse the statement.
    """
    try:
        import sqlglot

        parsed = sqlglot.parse_one(sql)
        return parsed.sql(normalize=True)
    except Exception:  # noqa: BLE001
        return re.sub(r"\s+", " ", sql.strip().lower())


class _Repo(Protocol):
    async def create(self, **fields: Any) -> dict[str, Any]: ...
    async def list(
        self,
        tenant_id: str,
        workspace_id: uuid.UUID,
        *,
        quality: str | None,
        dataset_id: uuid.UUID | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...
    async def get(self, example_id: uuid.UUID) -> dict[str, Any] | None: ...
    async def _review_snapshot(self, example_id: uuid.UUID) -> tuple[dict[str, Any], str]: ...
    async def update_quality(
        self,
        example_id: uuid.UUID,
        quality: str,
        *,
        embedding: list[float] | None = None,
        expected_source: tuple[str, str] | None = None,
        expected_quality: str | None = None,
        expected_review_version: str | None = None,
    ) -> dict[str, Any]: ...


@service_bean(name="structured.ExamplesService")
class ExamplesService:
    """Business logic for the examples knowledge base."""

    def __init__(self, repo: ExamplesRepository, embedder: Embedder | None = None) -> None:
        self._repo: _Repo = repo
        self._embedder = embedder  # may be None — embeddings stay NULL

    async def create(
        self,
        tenant_id: str,
        workspace_id: uuid.UUID,
        body: ExampleCreate,
        *,
        source: str = "USER_CURATED",
        quality: str = "PROPOSED",
        actor: str = "user",
    ) -> dict[str, Any]:
        """Insert a new example row.

        :param tenant_id: tenant identifier from request context
        :param workspace_id: workspace UUID
        :param body: validated create payload
        :param source: USER_CURATED (default) or AGENT_LEARNED
        :param quality: PROPOSED (default) — operator upgrades to APPROVED
        :param actor: who created the example (user / agent)
        :return: full example dict
        """
        normalised = _normalise_sql(body.generated_sql)
        embedding = None
        if self._embedder is not None:
            embedding = await self._embedder.embed(body.question)
        return await self._repo.create(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            dataset_id=body.dataset_id,
            question=body.question,
            generated_sql=body.generated_sql,
            normalised_sql=normalised,
            source=source,
            quality=quality,
            citations_json=body.citations_json,
            created_by=actor,
            embedding=embedding,
        )

    async def list(
        self,
        tenant_id: str,
        workspace_id: uuid.UUID,
        *,
        quality: str | None = None,
        dataset_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List examples for a workspace, optionally filtered by quality or dataset."""
        return await self._repo.list(
            tenant_id,
            workspace_id,
            quality=quality,
            dataset_id=dataset_id,
            limit=limit,
        )

    async def get(self, example_id: uuid.UUID) -> dict[str, Any] | None:
        """Fetch a single example by id; returns None when not found."""
        return await self._repo.get(example_id)

    async def approve(self, example_id: uuid.UUID) -> dict[str, Any]:
        """Approve the recorded example and publish its compatible active vector atomically."""
        from pyfly.kernel import ServiceUnavailableException

        from flyquery.core.agents.model_bindings import embedding_for
        from flyquery.web.conventions.context import current_tenant_context

        row, review_version = await self._repo._review_snapshot(example_id)
        binding = embedding_for("structured.embedding")
        if binding is not None and binding.versioned:
            context = current_tenant_context()
            if context is None or (row["tenant_id"], str(row["workspace_id"])) != (
                context.tenant_id,
                str(context.workspace_id),
            ):
                raise ValueError("Example approval differs from its active native scope")
        source = (row["question"], row["generated_sql"])
        quality = row["quality"]
        embedding = await self._embedder.embed(source[0]) if self._embedder is not None else None
        if binding is not None and binding.versioned and embedding is None:
            raise ServiceUnavailableException(
                "Configure the active embedding connection before approving an example",
                code="INDEX_EMBEDDING_REQUIRED",
            )
        return await self._repo.update_quality(
            example_id,
            "APPROVED",
            embedding=embedding,
            expected_source=source,
            expected_quality=quality,
            expected_review_version=review_version,
        )

    async def reject(self, example_id: uuid.UUID) -> dict[str, Any]:
        """Reject an example (set quality=REJECTED)."""
        return await self._repo.update_quality(example_id, "REJECTED")

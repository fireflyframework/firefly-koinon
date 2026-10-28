# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded sidecar embedding builds preserve every currently serving vector."""

from hashlib import sha256
from math import isfinite
from numbers import Real

from flyquery.core.services.ingestion.stages.embed import _build_embed_text


def content_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class VersionedIndexService:
    def __init__(self, repository):
        self.repository = repository

    async def step(
        self,
        *,
        tenant_id,
        workspace_id,
        set_id,
        embedder,
        dimensions,
        model,
        batch_size=32,
        validate_write=None,
    ):
        if isinstance(batch_size, bool) or not 1 <= batch_size <= 64 or not 64 <= dimensions <= 1536:
            raise ValueError("A structured index requires a bounded batch and compatible native width")
        scope = {"tenant_id": tenant_id, "workspace_id": workspace_id, "set_id": set_id}
        batch = await self.repository.missing(**scope, limit=batch_size)
        rows = []
        if batch:
            texts = [row["question"] if row["kind"] == "example" else _build_embed_text(row) for row in batch]
            if any(len(value) > 16000 for value in texts) or sum(map(len, texts)) > 256000:
                raise ValueError("Embedding source text exceeds the bounded native index batch")
            vectors = (await embedder.embed(texts)).embeddings
            if len(vectors) != len(batch) or any(
                len(vector) != dimensions
                or not any(vector)
                or any(
                    isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value)
                    for value in vector
                )
                for vector in vectors
            ):
                raise ValueError("The selected native embedding provider returned incompatible vectors")
            rows = [
                {
                    "id": row["id"],
                    "kind": row["kind"],
                    "content_hash": row.get("source_hash")
                    or content_hash(text + "\x1f" + row.get("generated_sql", "")),
                    "embedding": list(vector) + [0.0] * (1536 - dimensions),
                    "model": model,
                }
                for row, text, vector in zip(batch, texts, vectors, strict=True)
            ]
            if validate_write is not None:
                await validate_write()
            await self.repository.upsert(**scope, rows=rows)
        remaining = await self.repository.missing(**scope, limit=1)
        counts = await self.repository.counts(**scope)
        return {"written": len(rows), "complete": not remaining, **counts}

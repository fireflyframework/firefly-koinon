# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
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

"""Generic embedder backed by fireflyframework-agentic's provider registry.

This module delegates the actual embedding call to one of the eight
provider adapters shipped by ``pyfly.agentic.embeddings``,
so a local Ollama, an air-gapped Bedrock deployment, or a regulated
customer running Azure OpenAI are all supported through one surface:

* ``ollama``  -- local, default for tests + dev
* ``openai``  -- text-embedding-3-{small,large}
* ``cohere``  -- embed-english-v3.0
* ``voyage``  -- voyage-3, voyage-large-2
* ``azure``   -- Azure OpenAI deployments
* ``google``  -- Vertex AI text-embedding models
* ``mistral`` -- mistral-embed
* ``bedrock`` -- AWS Titan / Cohere on Bedrock
* ``null``    -- explicit "no embeddings" mode for BM25-only retrieval

Vector padding
--------------
The schema column is ``vector(<settings.embedding_dimensions>)`` (default
1536, matching the lock-step canon migration). Some providers emit
smaller vectors -- Ollama ``nomic-embed-text`` is 768, Cohere v3 is
1024. The persistence helper zero-pads them to the configured column
dim. Cosine similarity ranking is preserved because zero coordinates
contribute zero to both the dot product and the L2 norms.

Async + sync surface
--------------------
The public ``Embedder`` protocol is async-first to match the rest of
the codebase. A synchronous mirror (``embed_sync`` / ``embed_batch_sync``)
is exposed for CLI scripts and unit tests; it just wraps
``asyncio.run`` and is safe to call from any thread that doesn't
already have a running event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
from hashlib import sha256
from json import dumps
from math import isfinite
from numbers import Real
from re import fullmatch
from typing import TYPE_CHECKING, Any, Protocol

from pyfly.kernel import ServiceUnavailableException

from flyquery.core.agents.model_bindings import current_scope, embedding_for

if TYPE_CHECKING:
    from flyquery.config import FlyquerySettings

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Public Protocol
# ----------------------------------------------------------------------


class Embedder(Protocol):
    """Async embedder contract used by the embed stage + grounding agent."""

    @property
    def model(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    async def embed(self, text: str) -> list[float] | None: ...

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]: ...

    def embed_sync(self, text: str) -> list[float] | None: ...

    def embed_batch_sync(self, texts: list[str]) -> list[list[float] | None]: ...


# ----------------------------------------------------------------------
# Null embedder -- always returns None
# ----------------------------------------------------------------------


class NullEmbedder:
    """Embedder that always returns ``None``.

    Selected when ``embedding_provider="null"`` OR when the provider's
    API key / endpoint isn't reachable. Lets ingestion still complete
    and the schema KB is queryable -- retrieval just falls back to
    BM25 over ``content_tsv``.
    """

    def __init__(self, dimensions: int = 1536, model: str = "null") -> None:
        self._dim = dimensions
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dim

    def _standalone_only(self) -> None:
        if current_scope() is not None:
            embedding_for("structured.embedding")
            raise ServiceUnavailableException(
                "The structured vector space is disabled; qualify its embedding connection and reindex",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )

    async def embed(self, text: str) -> list[float] | None:  # noqa: ARG002
        self._standalone_only()
        return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        if texts:
            self._standalone_only()
        return [None] * len(texts)

    def embed_sync(self, text: str) -> list[float] | None:
        self._standalone_only()
        return None

    def embed_batch_sync(self, texts: list[str]) -> list[list[float] | None]:
        if texts:
            self._standalone_only()
        return [None] * len(texts)


# ----------------------------------------------------------------------
# fireflyframework-agentic-backed embedder
# ----------------------------------------------------------------------


class FireflyEmbedder:
    """Wraps a ``pyfly.agentic.embeddings.BaseEmbedder``.

    Adapts the ff-agentic ``async embed/embed_one`` surface to flyquery's
    ``embed/embed_batch`` Protocol, zero-pads to the configured column
    dimension, and exposes sync helpers for non-async callers.
    """

    def __init__(
        self,
        *,
        inner: Any,  # pyfly.agentic.embeddings.BaseEmbedder
        target_dim: int,
        native_dim: int,
        allow_provider_fallback: bool = False,
        embedding_model: str | None = None,
        space_id: str | None = None,
    ) -> None:
        self._inner = inner
        self._require_binding = inner is None
        self._target_dim = target_dim
        self._native_dim = native_dim
        self._allow_provider_fallback = allow_provider_fallback
        self._embedding_model = embedding_model
        self._space_id = space_id

    @property
    def model(self) -> str:
        binding = embedding_for("structured.embedding")
        if binding is not None and binding.versioned:
            return binding.embedder.model
        return (
            self._inner.model if self._inner is not None else (self._embedding_model or "").partition(":")[2]
        )

    @property
    def dimensions(self) -> int:
        return self._target_dim

    def _pad(self, vec: list[float]) -> list[float]:
        """Zero-pad or truncate ``vec`` to the column dim.

        Producers return native-dimensional vectors; the column is
        fixed-size. Pad with zeros when smaller (cosine-preserving),
        truncate when larger (information loss but rare).
        """
        n = len(vec)
        binding = embedding_for("structured.embedding")
        native_dim = binding.dimensions if binding is not None and binding.versioned else self._native_dim
        if current_scope() is not None and (
            n != native_dim
            or not any(vec)
            or any(
                isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) for value in vec
            )
        ):
            raise ServiceUnavailableException(
                "The selected embedding provider returned incompatible or invalid vectors; qualify a reindex",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        if n == self._target_dim:
            return vec
        if n < self._target_dim:
            return list(vec) + [0.0] * (self._target_dim - n)
        return list(vec[: self._target_dim])

    async def embed(self, text: str) -> list[float] | None:
        inner = self._request_inner()
        try:
            vec = await inner.embed_one(text)
        except Exception as exc:  # noqa: BLE001
            if not self._allow_provider_fallback or current_scope() is not None:
                raise ServiceUnavailableException(
                    "The configured embedding provider failed; verify its endpoint/model",
                    code="EMBEDDING_PROVIDER_UNAVAILABLE",
                ) from exc
            logger.warning("embedder=%s embed_one failed: %s", self._inner.model, exc)
            return None
        return self._pad(vec)

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        if not texts:
            return []
        inner = self._request_inner()
        try:
            result = await inner.embed(texts)
        except Exception as exc:  # noqa: BLE001
            if not self._allow_provider_fallback or current_scope() is not None:
                raise ServiceUnavailableException(
                    "The configured embedding provider failed; verify its endpoint/model",
                    code="EMBEDDING_PROVIDER_UNAVAILABLE",
                ) from exc
            logger.warning("embedder=%s embed batch failed: %s", self._inner.model, exc)
            return [None] * len(texts)
        return [self._pad(v) for v in result.embeddings]

    def _request_inner(self) -> Any:
        binding = embedding_for("structured.embedding")
        if binding is None:
            if self._require_binding:
                raise ServiceUnavailableException(
                    "Select a compatible authorized structured embedding connection",
                    code="KNOWLEDGE_EMBEDDING_BINDING_REQUIRED",
                )
            return self._inner
        if binding.versioned:
            if (
                not fullmatch(r"fs-[0-9a-f]{32}", binding.space_id)
                or binding.storage_dimensions != self._target_dim
                or binding.storage_dimensions != 1536
                or not 64 <= binding.dimensions <= binding.storage_dimensions
                or binding.embedder.dimensions != binding.dimensions
                or binding.embedding_model.partition(":")[2] != binding.embedder.model
            ):
                raise ServiceUnavailableException(
                    "Select a qualified versioned structured embedding space",
                    code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
                )
            return binding.embedder
        if (
            self._space_id is None
            or binding.space_id != self._space_id
            or binding.embedding_model != self._embedding_model
            or binding.dimensions != self._native_dim
            or binding.storage_dimensions != self._target_dim
            or binding.embedder.dimensions != self._native_dim
            or binding.embedder.model != self.model
            or self._native_dim > self._target_dim
        ):
            raise ServiceUnavailableException(
                "The selected structured embedding connection requires a qualified compatible space and reindex",
                code="KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED",
            )
        return binding.embedder

    def embed_sync(self, text: str) -> list[float] | None:
        return asyncio.run(self.embed(text))

    def embed_batch_sync(self, texts: list[str]) -> list[list[float] | None]:
        return asyncio.run(self.embed_batch(texts))


# ----------------------------------------------------------------------
# Factory
# ----------------------------------------------------------------------


def build_embedder(settings: FlyquerySettings) -> Embedder:
    """Build the configured embedder, with a Null fallback on any error.

    The factory inspects ``settings.embedding_provider`` and pulls the
    matching adapter from ``pyfly.agentic.embeddings.providers``.
    A missing API key / unreachable Ollama is logged + downgraded to
    ``NullEmbedder`` so ingestion still completes.
    """
    provider = (settings.embedding_provider or "null").lower()
    target_dim = int(settings.embedding_dimensions)
    native_dim = int(getattr(settings, "embedding_native_dim", target_dim))
    model = settings.embedding_model

    if settings._require_model_bindings:
        return FireflyEmbedder(
            inner=None,
            target_dim=target_dim,
            native_dim=native_dim,
            embedding_model=f"{provider}:{model}",
            space_id=deployment_embedding_space(settings),
        )

    if provider == "null":
        return NullEmbedder(dimensions=target_dim, model="null")

    try:
        inner = _construct_inner(provider, model, native_dim, settings)
    except Exception as exc:  # noqa: BLE001
        if not settings.allow_provider_fallback:
            raise ServiceUnavailableException(
                "The configured embedding provider is unavailable; verify its credentials/endpoint/model",
                code="EMBEDDING_PROVIDER_UNAVAILABLE",
            ) from exc
        logger.warning(
            "embedder provider=%s model=%s unavailable (%s) -- falling back to NullEmbedder. "
            "Retrieval will use BM25 over content_tsv only.",
            provider,
            model,
            exc,
        )
        return NullEmbedder(dimensions=target_dim, model=f"{provider}:{model}:disabled")

    return FireflyEmbedder(
        inner=inner,
        target_dim=target_dim,
        native_dim=native_dim,
        allow_provider_fallback=settings.allow_provider_fallback,
        embedding_model=f"{provider}:{model}",
        space_id=deployment_embedding_space(settings),
    )


def deployment_embedding_space(settings: FlyquerySettings) -> str:
    """Fingerprint the retained deployment's space; changing it requires reindex qualification."""
    values = {
        "provider": settings.embedding_provider,
        "model": settings.embedding_model,
        "native_dimensions": settings.embedding_native_dim,
        "storage_dimensions": settings.embedding_dimensions,
        "endpoint": (settings.embedding_base_url or "").rstrip("/"),
    }
    return "structured-" + sha256(dumps(values, sort_keys=True).encode()).hexdigest()


def _construct_inner(
    provider: str,
    model: str,
    native_dim: int,
    settings: FlyquerySettings,
) -> Any:
    """Instantiate the right ``pyfly.agentic.embeddings`` adapter."""
    base_url = settings.embedding_base_url

    if provider == "ollama":
        from pyfly.agentic.embeddings.providers.ollama import OllamaEmbedder

        return OllamaEmbedder(
            model=model,
            dimensions=native_dim,
            base_url=base_url or "http://localhost:11434",
        )
    if provider == "openai":
        from pyfly.agentic.embeddings.providers.openai import OpenAIEmbedder

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set")
        return OpenAIEmbedder(model=model, dimensions=native_dim)
    if provider == "cohere":
        from pyfly.agentic.embeddings.providers.cohere import CohereEmbedder

        if not os.environ.get("COHERE_API_KEY"):
            raise RuntimeError("COHERE_API_KEY not set")
        return CohereEmbedder(model=model, dimensions=native_dim)
    if provider == "voyage":
        from pyfly.agentic.embeddings.providers.voyage import VoyageEmbedder

        if not os.environ.get("VOYAGE_API_KEY"):
            raise RuntimeError("VOYAGE_API_KEY not set")
        return VoyageEmbedder(model=model, dimensions=native_dim)
    if provider == "mistral":
        from pyfly.agentic.embeddings.providers.mistral import MistralEmbedder

        if not os.environ.get("MISTRAL_API_KEY"):
            raise RuntimeError("MISTRAL_API_KEY not set")
        return MistralEmbedder(model=model, dimensions=native_dim)
    if provider == "azure":
        from pyfly.agentic.embeddings.providers.azure import AzureEmbedder

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT not set")
        return AzureEmbedder(
            model=model,
            dimensions=native_dim,
            azure_endpoint=endpoint,
            api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        )
    if provider == "google":
        from pyfly.agentic.embeddings.providers.google import GoogleEmbedder

        return GoogleEmbedder(model=model, dimensions=native_dim)
    if provider == "bedrock":
        from pyfly.agentic.embeddings.providers.bedrock import BedrockEmbedder

        return BedrockEmbedder(model=model, dimensions=native_dim)
    raise ValueError(f"Unknown embedding_provider={provider!r}")

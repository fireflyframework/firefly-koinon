# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Root composition owns authorization and connection lifetimes; domains borrow values."""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from flycanon.core.agents.model_bindings import EmbeddingBinding as DocumentEmbeddingBinding
from flycanon.core.agents.model_bindings import ModelBinding as DocumentModelBinding
from flyquery.core.agents.model_bindings import EmbeddingBinding as StructuredEmbeddingBinding
from flyquery.core.agents.model_bindings import ModelBinding as StructuredModelBinding


@dataclass(frozen=True)
class DomainConnections:
    models: Mapping[str, DocumentModelBinding | StructuredModelBinding]
    embeddings: Mapping[str, DocumentEmbeddingBinding | StructuredEmbeddingBinding]


class KnowledgeConnectionResolver(ABC):
    @abstractmethod
    def resolve(
        self,
        *,
        domain: str,
        tenant_id: str,
        workspace_id: str,
        subject: str,
        purpose: str,
        roles: tuple[str, ...],
        catalog_workspace_id: str | None = None,
    ) -> AbstractAsyncContextManager[DomainConnections]:
        """Authorize the verified native scope and hold every public native client lifetime.

        A composing application must bind this port to its selected connection resolver.
        It may also explicitly push already borrowed domain bindings around a tool/stream.
        Neither path may resolve deployment defaults for an unconfigured product role.
        """
        ...

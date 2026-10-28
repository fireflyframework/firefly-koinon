# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Open only the selected native embedding adapter with explicit credentials."""

from contextlib import asynccontextmanager
from inspect import signature

from pyfly.kernel import ServiceUnavailableException


@asynccontextmanager
async def open_embedding(compiler, secrets, provider, model_id, dimensions):
    address = compiler.address(provider.kind, provider.base_url)
    if provider.kind not in {"ollama", "openai"}:
        raise ServiceUnavailableException(
            "This provider has no qualified native embedding adapter",
            code="KNOWLEDGE_EMBEDDING_BINDING_REQUIRED",
        )
    if provider.kind == "openai":
        from pyfly.agentic.embeddings.providers.openai import OpenAIEmbedder

        if "base_url" not in signature(OpenAIEmbedder).parameters:
            raise ServiceUnavailableException(
                "The native OpenAI embedding adapter cannot preserve an explicit endpoint; "
                "upgrade its public adapter support or select Ollama",
                code="EMBEDDING_ENDPOINT_UNSUPPORTED",
            )
    if provider.kind == "ollama":
        from pyfly.agentic.embeddings.providers.ollama import OllamaEmbedder

        has_secret = bool(getattr(provider, "secret_ciphertext", None))
        supports_secret = "api_key" in signature(OllamaEmbedder).parameters
        if has_secret and not supports_secret:
            raise ServiceUnavailableException(
                "The native Ollama embedding adapter cannot forward the selected credential; "
                "use a qualified explicit credential adapter",
                code="EMBEDDING_CREDENTIAL_UNSUPPORTED",
            )
        secret = (
            secrets.decrypt(provider.tenant_id, provider.id, provider.secret_ciphertext)
            if has_secret
            else None
        )
        try:
            embedder = OllamaEmbedder(
                model=model_id,
                dimensions=dimensions,
                base_url=address.removesuffix("/v1"),
                **({"api_key": secret} if supports_secret else {}),
            )
        finally:
            del secret
    else:
        from pyfly.agentic.embeddings.providers.openai import OpenAIEmbedder

        if not provider.secret_ciphertext:
            raise ServiceUnavailableException(
                "Configure the selected embedding provider credential",
                code="KNOWLEDGE_PROVIDER_CREDENTIAL_REQUIRED",
            )
        secret = secrets.decrypt(provider.tenant_id, provider.id, provider.secret_ciphertext)
        try:
            embedder = OpenAIEmbedder(model=model_id, dimensions=dimensions, api_key=secret, base_url=address)
        finally:
            del secret
    async with embedder:
        yield embedder

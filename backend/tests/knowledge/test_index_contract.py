# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from pyfly.kernel import InvalidRequestException

from koinon.knowledge.indexes.dtos import IndexCreateInput, IndexPlanInput
from koinon.knowledge.indexes.probe import qualify_embedding


def request(**changes):
    return dict(
        workspace_id="workspace", domain="documents", provider_id="owned", model_id="embedding", **changes
    )


def test_index_contract_requires_explicit_revision_and_actual_model_selection():
    with pytest.raises(ValidationError):
        IndexCreateInput.model_validate(request())
    data = IndexCreateInput.model_validate(
        request(expected_active_id=None, expected_connection_revision=None)
    )
    assert data.batch_size == 32
    for changes in ({"batch_size": 65}, {"batch_size": True}, {"space_id": "invented"}):
        values = request(expected_active_id=None, expected_connection_revision=None)
        values.update(changes)
        with pytest.raises(ValidationError):
            IndexCreateInput.model_validate(values)
    with pytest.raises(ValidationError):
        IndexPlanInput.model_validate({**request(), "expected_dimensions": True})


@pytest.mark.parametrize("domain,native,storage", [("documents", 768, 768), ("structured", 768, 1536)])
async def test_probe_derives_native_width_and_closes_public_resource(domain, native, storage):
    state = []
    embedder = SimpleNamespace(embed=AsyncMock(return_value=SimpleNamespace(embeddings=[[0.5] * native] * 2)))

    @asynccontextmanager
    async def opened():
        state.append("opened")
        try:
            yield embedder
        finally:
            state.append("closed")

    result = await qualify_embedding(opened(), domain=domain)
    assert result == {"dimensions": native, "storage_dimensions": storage, "qualification": "probe_passed"}
    assert state == ["opened", "closed"]
    texts = embedder.embed.await_args.args[0]
    assert len(texts) == 2 and max(map(len, texts)) < 256


@pytest.mark.parametrize(
    "vectors", [[], [[0.1] * 768], [[0.0] * 768] * 2, [[float("nan")] * 768] * 2, [[0.2] * 768, [0.2] * 769]]
)
async def test_probe_rejects_invalid_provider_vector_contract(vectors):
    @asynccontextmanager
    async def opened():
        yield SimpleNamespace(embed=AsyncMock(return_value=SimpleNamespace(embeddings=vectors)))

    with pytest.raises(InvalidRequestException):
        await qualify_embedding(opened(), domain="documents")


async def test_probe_does_not_silently_accept_asserted_or_structured_incompatible_width():
    @asynccontextmanager
    async def opened(width):
        yield SimpleNamespace(embed=AsyncMock(return_value=SimpleNamespace(embeddings=[[0.5] * width] * 2)))

    with pytest.raises(InvalidRequestException):
        await qualify_embedding(opened(768), domain="documents", expected_dimensions=1536)
    with pytest.raises(InvalidRequestException):
        await qualify_embedding(opened(3072), domain="structured")


async def test_custom_openai_embedding_endpoint_is_not_silently_replaced_by_native_default(monkeypatch):

    class LegacyNativeEmbedder:
        def __init__(self, model, dimensions=None, *, api_key=None, **kwargs):
            raise AssertionError("An unsupported native constructor must not be entered")

    monkeypatch.setattr("pyfly.agentic.embeddings.providers.openai.OpenAIEmbedder", LegacyNativeEmbedder)
    from koinon.knowledge.connections.embeddings import open_embedding

    compiler = SimpleNamespace(address=lambda kind, url: url)
    secrets = SimpleNamespace(decrypt=AsyncMock())
    provider = SimpleNamespace(
        id="provider",
        tenant_id="tenant",
        kind="openai",
        base_url="http://127.0.0.1:18888/v1",
        secret_ciphertext=b"encrypted",
    )
    from pyfly.kernel import ServiceUnavailableException

    with pytest.raises(ServiceUnavailableException) as error:
        async with open_embedding(compiler, secrets, provider, "embedding", None):
            pytest.fail("Unsupported native endpoint must not create a client")
    assert error.value.code == "EMBEDDING_ENDPOINT_UNSUPPORTED"
    secrets.decrypt.assert_not_called()


def test_activation_recovery_is_explicit_and_limited_to_known_actions():
    from koinon.knowledge.indexes.dtos import IndexActivateInput

    base = {"expected_revision": 1, "expected_active_id": None, "expected_connection_revision": None}
    assert IndexActivateInput.model_validate(base).recovery is None
    assert (
        IndexActivateInput.model_validate({**base, "recovery": "restore_previous"}).recovery
        == "restore_previous"
    )
    with pytest.raises(ValidationError):
        IndexActivateInput.model_validate({**base, "recovery": "drop"})


async def test_official_embedding_endpoint_cannot_inherit_ambient_provider_routing(monkeypatch):

    class LegacyNativeEmbedder:
        def __init__(self, model, dimensions=None, *, api_key=None, **kwargs):
            raise AssertionError("An unsupported native constructor must not be entered")

    monkeypatch.setattr("pyfly.agentic.embeddings.providers.openai.OpenAIEmbedder", LegacyNativeEmbedder)
    from unittest.mock import MagicMock

    from pyfly.kernel import ServiceUnavailableException

    from koinon.knowledge.connections.embeddings import open_embedding

    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:18888/ambient")
    provider = SimpleNamespace(
        id="provider",
        tenant_id="tenant",
        kind="openai",
        base_url="https://api.openai.com/v1",
        secret_ciphertext=b"encrypted",
    )
    secrets = SimpleNamespace(decrypt=MagicMock(return_value="explicit-owned-test-key"))
    with pytest.raises(ServiceUnavailableException) as error:
        async with open_embedding(
            SimpleNamespace(address=lambda kind, url: url), secrets, provider, "embedding", 768
        ):
            pytest.fail("A native adapter without explicit endpoint support must stay closed")
    assert error.value.code == "EMBEDDING_ENDPOINT_UNSUPPORTED"
    secrets.decrypt.assert_not_called()


async def test_native_openai_adapter_receives_selected_url_secret_width_and_closes_on_failure(monkeypatch):
    from unittest.mock import MagicMock

    from koinon.knowledge.connections.embeddings import open_embedding

    sdk = SimpleNamespace(
        embeddings=SimpleNamespace(
            create=AsyncMock(
                return_value=SimpleNamespace(data=[SimpleNamespace(index=0, embedding=[0.25] * 64)])
            )
        ),
        close=AsyncMock(),
    )
    constructor = MagicMock(return_value=sdk)
    monkeypatch.setattr("pyfly.agentic.embeddings.providers.openai.AsyncOpenAI", constructor)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:18888/ambient")
    provider = SimpleNamespace(
        id="provider",
        tenant_id="tenant",
        kind="openai",
        base_url="http://127.0.0.1:18888/selected/v1",
        secret_ciphertext=b"encrypted",
    )
    secrets = SimpleNamespace(decrypt=MagicMock(return_value="explicit-test-key"))
    with pytest.raises(RuntimeError, match="caller failed"):
        async with open_embedding(
            SimpleNamespace(address=lambda kind, url: url), secrets, provider, "text-embedding-3-small", 64
        ) as embedder:
            assert (await embedder.embed(["bounded facts"])).embeddings == [[0.25] * 64]
            raise RuntimeError("caller failed")
    constructor.assert_called_once_with(api_key="explicit-test-key", base_url=provider.base_url)
    assert sdk.embeddings.create.await_args.kwargs["dimensions"] == 64
    sdk.close.assert_awaited_once()


async def test_ollama_selected_credential_is_not_silently_ignored(monkeypatch):
    from unittest.mock import MagicMock

    from pyfly.kernel import ServiceUnavailableException

    from koinon.knowledge.connections.embeddings import open_embedding

    constructor = MagicMock(
        side_effect=AssertionError("Credential loss must fail before constructing a client")
    )
    monkeypatch.setattr("pyfly.agentic.embeddings.providers.ollama.OllamaEmbedder", constructor)
    provider = SimpleNamespace(
        id="provider",
        tenant_id="tenant",
        kind="ollama",
        base_url="http://127.0.0.1:11434/v1",
        secret_ciphertext=b"encrypted",
    )
    with pytest.raises(ServiceUnavailableException) as error:
        async with open_embedding(
            SimpleNamespace(address=lambda kind, url: url), None, provider, "embedding", 768
        ):
            pytest.fail("An unsupported selected credential cannot be ignored")
    assert error.value.code == "EMBEDDING_CREDENTIAL_UNSUPPORTED"
    constructor.assert_not_called()


async def test_public_native_ollama_binding_preserves_explicit_credential_endpoint_and_closure(monkeypatch):
    from unittest.mock import MagicMock

    import httpx
    from pyfly.agentic.embeddings.providers import ollama

    from koinon.knowledge.connections.embeddings import open_embedding

    original = httpx.AsyncClient
    clients, requests = [], []

    def respond(request):
        requests.append(request)
        assert str(request.url) == "http://127.0.0.1:18888/private/api/embed"
        assert request.headers["authorization"] == "Bearer selected-test-key"
        return httpx.Response(200, json={"embeddings": [[0.25] * 64]})

    def client(**kwargs):
        value = original(**kwargs, transport=httpx.MockTransport(respond))
        clients.append(value)
        return value

    monkeypatch.setattr(ollama.httpx, "AsyncClient", client)
    monkeypatch.setenv("OLLAMA_API_KEY", "ambient-must-not-be-used")
    provider = SimpleNamespace(
        id="provider",
        tenant_id="tenant",
        kind="ollama",
        base_url="http://127.0.0.1:18888/private/v1",
        secret_ciphertext=b"encrypted",
    )
    secrets = SimpleNamespace(decrypt=MagicMock(return_value="selected-test-key"))
    async with open_embedding(
        SimpleNamespace(address=lambda kind, url: url), secrets, provider, "embedding", 64
    ) as embedder:
        assert (await embedder.embed(["bounded facts"])).embeddings == [[0.25] * 64]
    assert len(requests) == 1 and all(value.is_closed for value in clients)
    secrets.decrypt.assert_called_once_with("tenant", "provider", b"encrypted")

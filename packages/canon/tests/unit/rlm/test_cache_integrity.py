# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Original-byte identity and authority boundaries for the extraction cache."""

from hashlib import sha256
from types import SimpleNamespace

import pytest
from pyfly.kernel import ServiceUnavailableException

from flycanon.core.services.ingestion.loaders import CsvLoader, LoaderRegistry, TextLoader
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
from flycanon.core.services.query.rlm.page_cache import MemoryPageCache
from flycanon.interfaces.enums import SourceKind


class Blobs:
    def __init__(self, content):
        self.content = content
        self.reads = 0

    def get_sync(self, key):
        self.reads += 1
        return self.content


class Sources:
    def __init__(self, row):
        self.row = row

    async def list_sources(self, **kwargs):
        return [self.row], 1


async def corpus(content, cache, *, tenant="t", workspace="w", source="s", loader=None, raw_metadata=True):
    metadata = {"_persisted_original": {"sha256": sha256(content).hexdigest(), "bytes": len(content)}}
    row = SimpleNamespace(
        id=source,
        tenant_id=tenant,
        workspace_id=workspace,
        kind="text",
        filename="doc.txt",
        object_store_key="private-key",
        content_sha256="normalized",
        metadata_json=metadata if raw_metadata else {},
    )
    registry = LoaderRegistry()
    registry.register(loader or TextLoader(), kind=SourceKind.text)
    blobs = Blobs(content)
    builder = CanonCorpusBuilder(
        source_repository=Sources(row),
        knowledge_repository=None,
        object_store=blobs,
        registry=registry,
        cache=cache,
    )
    return await builder.build(tenant_id=tenant, workspace_id=workspace), blobs


@pytest.mark.asyncio
async def test_distinct_raw_originals_with_equal_normalized_hash_do_not_share_pages():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    first, _ = await corpus(b"original alpha", cache, source="doc1")
    second, _ = await corpus(b"original beta", cache, source="doc2")
    assert first.pages("doc") == ["original alpha"]
    assert second.pages("doc") == ["original beta"]


@pytest.mark.asyncio
async def test_changed_original_for_same_logical_source_gets_its_own_extraction():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    first, _ = await corpus(b"original alpha", cache)
    second, _ = await corpus(b"original beta", cache)
    assert first.pages("doc") == ["original alpha"]
    assert second.pages("doc") == ["original beta"]
    assert len(cache._cache) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [{"tenant": "other"}, {"workspace": "other"}, {"source": "other"}])
async def test_scopes_and_logical_source_are_part_of_cache_identity(changed):
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    first, _ = await corpus(b"alpha", cache)
    second, _ = await corpus(b"alpha", cache, **changed)
    first.pages("doc")
    before = len(cache._cache)
    second.pages("doc")
    assert len(cache._cache) == before + 1


@pytest.mark.asyncio
async def test_actual_loader_configuration_changes_extraction_identity():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    first, _ = await corpus(b"a;b\n1;2", cache, loader=CsvLoader(delimiter=";"))
    second, _ = await corpus(b"a;b\n1;2", cache, loader=CsvLoader(delimiter=","))
    expected, _ = await corpus(b"a;b\n1;2", None, loader=CsvLoader(delimiter=","))
    first.pages("doc")
    assert second.pages("doc") == expected.pages("doc")
    assert len(cache._cache) == 2


@pytest.mark.asyncio
async def test_actual_loader_implementation_changes_extraction_identity():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    first, _ = await corpus(b"a;b\n1;2", cache)
    second, _ = await corpus(b"a;b\n1;2", cache, loader=CsvLoader(delimiter=";"))
    assert first.pages("doc") != second.pages("doc")
    assert len(cache._cache) == 2


@pytest.mark.asyncio
async def test_unidentified_custom_reader_is_not_shared_across_corpora():
    class CustomLoader(TextLoader):
        pass

    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    store, _ = await corpus(b"actual original", cache, loader=CustomLoader())
    assert store.pages("doc") == ["actual original"]
    assert not cache._cache


@pytest.mark.asyncio
async def test_unverified_original_metadata_bypasses_shared_cache():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    cache.set("normalized", ["wrong original"])
    store, _ = await corpus(b"actual original", cache, raw_metadata=False)
    assert store.pages("doc") == ["actual original"]
    assert len(cache._cache) == 1


@pytest.mark.asyncio
async def test_cached_pages_do_not_hide_original_corruption():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    first, _ = await corpus(b"alpha", cache)
    first.pages("doc")
    second, blobs = await corpus(b"alpha", cache)
    blobs.content = b"tampered"
    with pytest.raises(ServiceUnavailableException, match="original.*integrity"):
        second.pages("doc")


@pytest.mark.asyncio
async def test_authority_is_checked_before_even_memoized_pages_are_read():
    cache = MemoryPageCache(ttl_s=60, max_entries=20)
    store, _ = await corpus(b"alpha", cache)

    class Observer:
        async def authorize(self):
            pass

        def document_sync(self, *args):
            pass

    with provenance.observe(Observer(), tenant_id="t", workspace_id="w", actor="actor"):
        await provenance.authorize()
        assert store.pages("doc") == ["alpha"]
        store._load_pages = lambda _: pytest.fail("cached data accessed before current authorization")
        with pytest.raises(ServiceUnavailableException, match="authority"):
            store.pages("doc")


@pytest.mark.asyncio
async def test_changed_scope_cannot_read_previously_memoized_pages():
    store, blobs = await corpus(b"alpha", MemoryPageCache(ttl_s=60, max_entries=20))
    assert store.pages("doc") == ["alpha"]

    class Observer:
        async def authorize(self):
            pass

        def document_sync(self, *args):
            pytest.fail("foreign-scope pages must never enter evidence")

    with provenance.observe(Observer(), tenant_id="other", workspace_id="w", actor="actor"):
        await provenance.authorize()
        with pytest.raises(ServiceUnavailableException, match="scope mismatch"):
            store.pages("doc")
    assert blobs.reads == 1

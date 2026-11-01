# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Controlled SDK protocol tests; no credentials, sockets or provider services."""

from types import SimpleNamespace

import pytest
from koinon_storage.cloud import CloudProfile, CloudStore, ObjectCollisionError, ObjectTooLargeError


class ProviderError(Exception):
    def __init__(self, status):
        self.status_code = self.code = status
        super().__init__("secret-provider-endpoint-and-token")


class Objects(dict):
    def __init__(self):
        super().__init__()
        self.metadata = {}


class GcsBlob:
    def __init__(self, objects, name):
        self.objects, self.name = objects, name
        self.generation, self.metadata = 1, {}
        self.size = 0

    def upload_from_string(self, data, **kwargs):
        assert kwargs["if_generation_match"] == 0 and kwargs["retry"] is None
        assert kwargs["timeout"] == 3
        if self.name in self.objects:
            raise ProviderError(412)
        self.objects[self.name] = data
        self.objects.metadata[self.name] = self.metadata

    def upload_from_file(self, source, **kwargs):
        data = b"".join(iter(lambda: source.read(65536), b""))
        assert len(data) == kwargs.pop("size")
        assert kwargs.pop("rewind") is False
        assert kwargs.pop("checksum") == "auto"
        self.upload_from_string(data, **kwargs)

    def download_to_file(self, target, **kwargs):
        assert kwargs.pop("checksum") == "auto"
        target.write(self.download_as_bytes(**kwargs))

    def reload(self, **kwargs):
        if self.name not in self.objects:
            raise ProviderError(404)
        self.size = len(self.objects[self.name])
        self.metadata = self.objects.metadata.get(self.name, {})
        self.content_type, self.etag, self.updated = "text/plain", "etag", None

    def download_as_bytes(self, **kwargs):
        assert kwargs["if_generation_match"] == 1 and kwargs["retry"] is None
        return self.objects[self.name][kwargs["start"] : kwargs["end"] + 1]

    def delete(self, **kwargs):
        if self.name not in self.objects:
            raise ProviderError(404)
        del self.objects[self.name]


class GcsClient:
    def __init__(self):
        self.objects = Objects()

    def bucket(self, name):
        assert name == "owned-private"
        return SimpleNamespace(blob=lambda key: GcsBlob(self.objects, key))


class AzureBlob:
    def __init__(self, objects, name):
        self.objects, self.name = objects, name

    def upload_blob(self, data, **kwargs):
        assert kwargs["overwrite"] is False
        assert kwargs["timeout"] == 3 and kwargs["max_concurrency"] == 1
        if self.name in self.objects:
            raise ProviderError(409)
        if hasattr(data, "read"):
            data = b"".join(iter(lambda: data.read(65536), b""))
            assert len(data) == kwargs["length"]
        self.objects[self.name] = data
        self.objects.metadata[self.name] = kwargs["metadata"]

    def get_blob_properties(self, **kwargs):
        if self.name not in self.objects:
            raise ProviderError(404)
        return SimpleNamespace(
            size=len(self.objects[self.name]),
            metadata=self.objects.metadata.get(self.name, {}),
            etag="etag",
            content_settings=SimpleNamespace(content_type="text/plain"),
            last_modified=None,
        )

    def download_blob(self, **kwargs):
        assert kwargs["etag"] == "etag" and kwargs["max_concurrency"] == 1
        data = self.objects[self.name][: kwargs["length"]]
        return SimpleNamespace(readall=lambda: data, chunks=lambda: iter((data,)))

    def delete_blob(self, **kwargs):
        if self.name not in self.objects:
            raise ProviderError(404)
        del self.objects[self.name]


class AzureClient:
    def __init__(self):
        self.objects = Objects()

    def get_blob_client(self, container, blob):
        assert container == "owned-private"
        return AzureBlob(self.objects, blob)


@pytest.fixture(params=["azure", "gcs"])
def store(request):
    client = AzureClient() if request.param == "azure" else GcsClient()
    return CloudStore(
        CloudProfile(
            backend=request.param,
            azure_account_url="https://owned.blob.core.windows.net",
            azure_container="owned-private",
            azure_prefix="retained",
            gcs_bucket="owned-private",
            gcs_prefix="retained",
            request_timeout_seconds=3,
            max_object_bytes=32,
        ),
        client=client,
    )


async def test_immutable_create_verifies_bytes_and_retries_without_overwrite(store):
    await store.put("tenant/source/1", b"original", "text/plain")
    await store.put("tenant/source/1", b"original", "text/plain")
    with pytest.raises(ObjectCollisionError):
        await store.put("tenant/source/1", b"replacement")
    assert await store.get_bounded("tenant/source/1", 8) == b"original"
    assert store._client.objects == {"retained/tenant/source/1": b"original"}


async def test_bounded_reads_missing_delete_and_oversize_write(store):
    await store.put("tenant/source/1", b"original")
    with pytest.raises(ObjectTooLargeError):
        await store.get_bounded("tenant/source/1", 7)
    with pytest.raises(ObjectTooLargeError):
        await store.put("tenant/source/2", b"x" * 33)
    await store.delete("tenant/source/1")
    await store.delete("tenant/source/1")
    with pytest.raises(FileNotFoundError):
        await store.get_bounded("tenant/source/1", 10)


@pytest.mark.parametrize("key", ["/absolute", "../escape", "a/../escape", "a//b", "a\\b", "a\x00b"])
async def test_key_guards_happen_before_sdk_access(store, key):
    with pytest.raises(ValueError):
        await store.put(key, b"original")
    assert not store._client.objects


@pytest.mark.parametrize(
    "changes",
    [
        {"azure_account_url": "http://cloud.example"},
        {"azure_account_url": "https://cloud.example/?sig=secret"},
        {"gcs_endpoint_url": "http://cloud.example"},
        {"azure_prefix": "../escape"},
        {"gcs_prefix": "/absolute"},
        {"azure_container": ""},
        {"max_object_bytes": True},
        {"request_timeout_seconds": 0},
    ],
)
def test_profile_rejects_insecure_or_ambiguous_configuration(changes):
    values = dict(
        backend="azure",
        azure_account_url="https://owned.blob.core.windows.net",
        azure_container="owned-private",
    )
    with pytest.raises(ValueError):
        CloudProfile(**(values | changes))


def test_clients_are_lazy_and_emulator_requires_explicit_loopback():
    store = CloudStore(
        CloudProfile(backend="gcs", gcs_bucket="owned-private", gcs_endpoint_url="http://127.0.0.1:4443")
    )
    assert store._client is None


async def test_provider_error_is_sanitized(store):
    store._client = SimpleNamespace(
        bucket=lambda name: (_ for _ in ()).throw(ProviderError(403)),
        get_blob_client=lambda **kwargs: (_ for _ in ()).throw(ProviderError(403)),
    )
    with pytest.raises(OSError, match="Cloud object storage request failed") as error:
        await store.get_bounded("tenant/source/1", 8)
    assert "secret" not in str(error.value)


async def test_write_verification_rejects_corrupted_provider_bytes(store):
    original = store.get_bounded

    async def corrupt(key, limit):
        return b"corrupt!"

    store.get_bounded = corrupt
    with pytest.raises(OSError, match="verification"):
        await store.put("tenant/source/1", b"original")
    store.get_bounded = original


async def test_cancellation_drains_inflight_sdk_write_before_returning(store):
    import asyncio
    import threading

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def operation():
        entered.set()
        release.wait(2)
        finished.set()

    task = asyncio.create_task(store._run(operation))
    await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


async def test_empty_objects_round_trip_without_invalid_range(store):
    await store.put("tenant/empty", b"")
    assert await store.get_bounded("tenant/empty", 0) == b""


async def test_gcs_large_upload_aborts_its_session_after_transport_failure(monkeypatch):
    import requests

    calls = []

    class Blob:
        metadata = None

        def create_resumable_upload_session(self, **kwargs):
            assert kwargs["if_generation_match"] == 0 and kwargs["size"] == 9 * 1024 * 1024
            assert kwargs["retry"] is None and kwargs["timeout"] == 3
            return "https://storage.googleapis.com/upload/session/opaque"

    class Transport:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def put(self, url, **kwargs):
            assert kwargs["timeout"] == 3
            calls.append("put")
            raise requests.Timeout("secret-endpoint")

        def delete(self, url, **kwargs):
            assert kwargs["timeout"] == 3
            calls.append("abort")

    monkeypatch.setattr(requests, "Session", Transport)
    client = SimpleNamespace(bucket=lambda name: SimpleNamespace(blob=lambda key: Blob()))
    store = CloudStore(
        CloudProfile(backend="gcs", gcs_bucket="owned-private", request_timeout_seconds=3), client=client
    )
    with pytest.raises(OSError, match="request failed"):
        await store.put("tenant/large", b"x" * (9 * 1024 * 1024))
    assert calls == ["put", "abort"]


async def test_ambient_gcs_endpoint_cannot_silently_redirect_storage(monkeypatch):
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://remote.example")
    store = CloudStore(CloudProfile(backend="gcs", gcs_bucket="owned-private"))
    with pytest.raises(OSError, match="request failed"):
        await store.put("tenant/one", b"original")
    assert store._client is None


async def test_read_rechecks_recorded_digest_after_same_length_corruption(store):
    await store.put("tenant/source/1", b"original")
    store._client.objects["retained/tenant/source/1"] = b"tampered"
    with pytest.raises(OSError, match="verification"):
        await store.get_bounded("tenant/source/1", 8)
    with pytest.raises(OSError, match="verification"):
        store.get_sync("tenant/source/1")


async def test_different_length_collision_preserves_original(store):
    await store.put("tenant/source/1", b"original")
    with pytest.raises(ObjectCollisionError):
        await store.put("tenant/source/1", b"new")
    assert await store.get("tenant/source/1") == b"original"


async def test_repeated_cancellation_still_drains_sdk_work(store):
    import asyncio
    import threading

    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def work():
        entered.set()
        release.wait(2)
        finished.set()

    task = asyncio.create_task(store._run(work))
    await asyncio.to_thread(entered.wait, 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


async def test_gcs_signed_download_is_scoped_and_ttl_is_bounded():
    signed = []

    class Blob:
        def generate_signed_url(self, **kwargs):
            signed.append(kwargs)
            return "https://storage.googleapis.com/owned-private/retained/tenant/source/1?signature=fixture"

    client = SimpleNamespace(
        bucket=lambda name: SimpleNamespace(blob=lambda key: signed.append(key) or Blob())
    )
    store = CloudStore(
        CloudProfile(backend="gcs", gcs_bucket="owned-private", gcs_prefix="retained"), client=client
    )
    assert "signature=fixture" in await store.presign_get("tenant/source/1", 60)
    assert signed[0] == "retained/tenant/source/1" and signed[1]["method"] == "GET"
    with pytest.raises(ValueError):
        await store.presign_get("tenant/source/1", 604801)


async def test_azure_legacy_connection_signs_without_requesting_delegation(monkeypatch):
    import azure.storage.blob

    arguments = []
    monkeypatch.setattr(
        azure.storage.blob,
        "generate_blob_sas",
        lambda **kwargs: arguments.append(kwargs) or "signature=fixture",
    )
    client = SimpleNamespace(
        account_name="owned",
        get_blob_client=lambda **kwargs: SimpleNamespace(
            url="https://owned.blob.core.windows.net/owned-private/" + kwargs["blob"]
        ),
    )
    store = CloudStore(
        CloudProfile(
            backend="azure",
            azure_account_url="https://owned.blob.core.windows.net",
            azure_container="owned-private",
            azure_prefix="retained",
        ),
        client=client,
    )
    store.connection_string = "AccountName=owned;AccountKey=fixture-from-test;DefaultEndpointsProtocol=https;"
    assert "signature=fixture" in await store.presign_get("tenant/source/1", 60)
    assert arguments[0]["account_key"] == "fixture-from-test"
    assert arguments[0]["blob_name"] == "retained/tenant/source/1"


async def test_listing_is_provider_scoped_and_bounded(store):
    options = []

    def values(*args, **kwargs):
        options.append(kwargs)
        return iter([SimpleNamespace(name="retained/tenant/source/1")])

    store._client = SimpleNamespace(
        list_blobs=values, get_container_client=lambda name: SimpleNamespace(list_blobs=values)
    )
    result = await store.list_metadata("tenant/source/")
    assert len(result) == 1
    assert (options[0].get("prefix") or options[0].get("name_starts_with")) == "retained/tenant/source/"
    assert options[0]["timeout"] == 3

    def too_many(*args, **kwargs):
        return (SimpleNamespace(name="retained/tenant/source/1") for _ in range(10001))

    store._client = SimpleNamespace(
        list_blobs=too_many, get_container_client=lambda name: SimpleNamespace(list_blobs=too_many)
    )
    with pytest.raises(OSError):
        await store.list_metadata("tenant/source/")


async def test_conflicting_azure_connection_string_cannot_redirect_the_profile():
    store = CloudStore(
        CloudProfile(
            backend="azure",
            azure_account_url="https://owned.blob.core.windows.net",
            azure_container="owned-private",
        )
    )
    store.connection_string = "AccountName=other;AccountKey=fixture-from-test;DefaultEndpointsProtocol=https;"
    with pytest.raises(OSError, match="request failed"):
        await store.put("tenant/source/1", b"original")
    assert store._client is None

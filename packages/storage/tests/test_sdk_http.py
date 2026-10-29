# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual optional SDKs against a fixture-owned loopback HTTP protocol server."""

import base64
import hashlib
import json
import threading
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from koinon_storage.cloud import CloudProfile, CloudStore, ObjectCollisionError, ObjectTooLargeError


@pytest.fixture
def endpoint():
    class Handler(BaseHTTPRequestHandler):
        objects = {}
        sessions = {}
        attributes = {}
        calls = []
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def respond(self, status, body=b"", **headers):
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers.items():
                self.send_header(name.replace("_", "-"), str(value))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def metadata(self, key):
            import google_crc32c

            data, content_type = self.objects[key]
            return dict(
                metadata=self.attributes.get(key, {}),
                name=key,
                bucket="owned-private",
                size=str(len(data)),
                generation="1",
                metageneration="1",
                contentType=content_type,
                etag="etag",
                updated="2026-10-28T12:00:00Z",
                crc32c=base64.b64encode(google_crc32c.Checksum(data).digest()).decode(),
                md5Hash=base64.b64encode(hashlib.md5(data).digest()).decode(),
            )

        def body(self):
            return self.rfile.read(int(self.headers.get("Content-Length", "0")))

        def do_POST(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            self.calls.append((self.command, parsed.path, dict(self.headers)))
            assert query.get("ifGenerationMatch") == ["0"]
            raw = self.body()
            if query.get("uploadType") == ["resumable"]:
                metadata = json.loads(raw)
                key = metadata["name"]
                if key in self.objects:
                    return self.respond(412, b'{"error":{"code":412}}', Content_Type="application/json")
                self.attributes[key] = metadata.get("metadata", {})
                self.sessions["1"] = (key, metadata.get("contentType", "application/octet-stream"))
                return self.respond(200, Location=f"http://127.0.0.1:{self.server.server_port}/session/1")
            message = BytesParser().parsebytes(
                b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + raw
            )
            metadata_part, data_part = message.get_payload()
            metadata = json.loads(metadata_part.get_payload(decode=True))
            key, data = metadata["name"], data_part.get_payload(decode=True)
            if key in self.objects:
                return self.respond(412, b'{"error":{"code":412}}', Content_Type="application/json")
            self.attributes[key] = metadata.get("metadata", {})
            self.objects[key] = (data, metadata.get("contentType", "application/octet-stream"))
            self.respond(200, json.dumps(self.metadata(key)).encode(), Content_Type="application/json")

        def do_PUT(self):
            path = unquote(urlsplit(self.path).path)
            self.calls.append((self.command, path, dict(self.headers)))
            data = self.body()
            if path.startswith("/session/"):
                key, content_type = self.sessions.pop(path.rsplit("/", 1)[-1])
                self.objects[key] = (data, content_type)
                return self.respond(
                    200, json.dumps(self.metadata(key)).encode(), Content_Type="application/json"
                )
            key = path.split("/owned-private/", 1)[-1]
            assert self.headers["If-None-Match"] == "*"
            if key in self.objects:
                return self.respond(409, b"", x_ms_error_code="BlobAlreadyExists")
            self.objects[key] = (data, self.headers.get("Content-Type", "application/octet-stream"))
            self.attributes[key] = {
                "sha256": self.headers.get("x-ms-meta-sha256"),
                "bytes": self.headers.get("x-ms-meta-bytes"),
            }
            self.respond(201, ETag='"etag"', x_ms_request_id="fixture")

        def do_HEAD(self):
            key = unquote(urlsplit(self.path).path).split("/owned-private/", 1)[-1]
            self.calls.append((self.command, key, dict(self.headers)))
            if key not in self.objects:
                return self.respond(404, x_ms_error_code="BlobNotFound")
            data, content_type = self.objects[key]
            self.respond(
                200,
                data,
                Content_Type=content_type,
                ETag='"etag"',
                Last_Modified="Wed, 28 Oct 2026 12:00:00 GMT",
                x_ms_blob_type="BlockBlob",
                x_ms_meta_sha256=self.attributes.get(key, {}).get("sha256", ""),
                x_ms_meta_bytes=self.attributes.get(key, {}).get("bytes", ""),
            )

        def do_GET(self):
            parsed = urlsplit(self.path)
            self.calls.append((self.command, parsed.path, dict(self.headers)))
            if "/o/" in parsed.path:
                key = unquote(parsed.path.split("/o/", 1)[1])
                media = parse_qs(parsed.query).get("alt") == ["media"]
            else:
                key, media = unquote(parsed.path).split("/owned-private/", 1)[-1], True
            if key not in self.objects:
                return self.respond(404, b'{"error":{"code":404}}', Content_Type="application/json")
            if not media:
                return self.respond(
                    200, json.dumps(self.metadata(key)).encode(), Content_Type="application/json"
                )
            data, content_type = self.objects[key]
            range_header = self.headers.get("Range") or self.headers.get("x-ms-range")
            if range_header:
                first, last = range_header.split("=", 1)[1].split("-")
                start, end = int(first), min(int(last), len(data) - 1)
                return self.respond(
                    206,
                    data[start : end + 1],
                    Content_Type=content_type,
                    Content_Range=f"bytes {start}-{end}/{len(data)}",
                    ETag='"etag"',
                    x_ms_blob_type="BlockBlob",
                )
            self.respond(200, data, Content_Type=content_type)

        def do_DELETE(self):
            parsed = urlsplit(self.path)
            key = unquote(
                parsed.path.split("/o/", 1)[-1]
                if "/o/" in parsed.path
                else parsed.path.split("/owned-private/", 1)[-1]
            )
            self.calls.append((self.command, key, dict(self.headers)))
            self.objects.pop(key, None)
            self.respond(204 if "/o/" in parsed.path else 202)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", Handler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


@pytest.mark.parametrize("backend", ["azure", "gcs"])
async def test_real_sdk_immutable_roundtrip_bounded_range_and_delete(endpoint, backend, monkeypatch):
    monkeypatch.delenv("STORAGE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("API_ENDPOINT_OVERRIDE", raising=False)
    url, handler = endpoint
    profile = CloudProfile(
        backend=backend,
        azure_account_url=url,
        azure_container="owned-private",
        azure_prefix="retained",
        gcs_bucket="owned-private",
        gcs_prefix="retained",
        gcs_endpoint_url=url,
        request_timeout_seconds=2,
    )
    store = CloudStore(profile)
    try:
        await store.put("tenant/source/1", b"original", "text/plain")
        await store.put("tenant/source/1", b"original", "text/plain")
        with pytest.raises(ObjectCollisionError):
            await store.put("tenant/source/1", b"changed!")
        with pytest.raises(ObjectTooLargeError):
            await store.get_bounded("tenant/source/1", 7)
        assert await store.get_bounded("tenant/source/1", 8) == b"original"
        assert store.get_sync("tenant/source/1") == b"original"
        assert await store.exists("tenant/source/1")
        await store.delete("tenant/source/1")
        assert not await store.exists("tenant/source/1")
        assert all("list" not in path and "create_container" not in path for _, path, _ in handler.calls)
    finally:
        await store.close()


async def test_real_gcs_sdk_large_upload_uses_completed_bounded_session(endpoint, monkeypatch):
    monkeypatch.delenv("STORAGE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("API_ENDPOINT_OVERRIDE", raising=False)
    url, handler = endpoint
    store = CloudStore(
        CloudProfile(
            backend="gcs", gcs_bucket="owned-private", gcs_endpoint_url=url, request_timeout_seconds=2
        )
    )
    data = b"x" * (9 * 1024 * 1024)
    try:
        await store.put("tenant/large", data, "application/octet-stream")
        assert await store.get_bounded("tenant/large", len(data)) == data
        assert handler.sessions == {}
        assert any(path == "/session/1" for _, path, _ in handler.calls)
    finally:
        await store.close()


@pytest.mark.parametrize("backend", ["azure", "gcs"])
async def test_actual_cloud_sdk_snapshots_reach_governed_duckdb_execution(endpoint, backend, monkeypatch):
    import io
    from pathlib import Path

    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    pytest.importorskip("flyquery")
    from flyquery.config import FlyquerySettings
    from flyquery.core.services.execution.duckdb_executor import (
        DuckDBExecutor,
        ExecutionError,
        ExecutionResult,
    )
    from flyquery.core.services.storage.object_store_factory import build_object_store

    monkeypatch.delenv("STORAGE_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("API_ENDPOINT_OVERRIDE", raising=False)
    url, handler = endpoint
    settings = FlyquerySettings(
        object_store=backend,
        object_store_azure_account_url=url,
        object_store_azure_container="owned-private",
        object_store_azure_prefix="snapshots",
        object_store_gcs_bucket="owned-private",
        object_store_gcs_prefix="snapshots",
        object_store_gcs_endpoint_url=url,
    )
    store = build_object_store(settings)
    output = io.BytesIO()
    pq.write_table(pa.Table.from_pylist([{"total": 25}, {"total": 50}]), output)
    await store.put("tenant/dataset/version.parquet", output.getvalue(), "application/vnd.apache.parquet")
    executor = DuckDBExecutor(settings)
    paths = []
    original = executor._sync_select

    def observe(sql, tables, engine, control):
        paths.extend(tables.values())
        assert all(
            Path(path).is_file() and Path(path).stat().st_mode & 0o777 == 0o600 for path in tables.values()
        )
        return original(sql, tables, engine, control)

    monkeypatch.setattr(executor, "_sync_select", observe)
    scheme = "azure" if backend == "azure" else "gs"
    try:
        result = await executor.execute(
            "SELECT SUM(total) AS total FROM orders",
            {"orders": f"{scheme}://owned-private/snapshots/tenant/dataset/version.parquet"},
        )
        assert isinstance(result, ExecutionResult) and result.rows == [{"total": 75}]
        assert paths and all(not Path(path).exists() for path in paths)
        rejected = await executor.execute(
            "SELECT * FROM orders",
            {"orders": f"{scheme}://other-private/snapshots/tenant/dataset/version.parquet"},
        )
        assert isinstance(rejected, ExecutionError)
        rejected_sql = await executor.execute(
            "SELECT * FROM read_csv_auto('https://external.example/data.csv')", {}
        )
        assert isinstance(rejected_sql, ExecutionError)
    finally:
        await store.native.close()

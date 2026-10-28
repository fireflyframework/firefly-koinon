# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run the shipped SPA/proxy template against an owned native nginx process."""

import http.client
import json
import os
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


class ApiFixture(BaseHTTPRequestHandler):
    stream_release = threading.Event()

    def respond(self):
        if self.path == "/api/v1/stream-fixture":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"data: first\n\n")
            self.wfile.flush()
            self.stream_release.wait(timeout=5)
            self.wfile.write(b"data: done\n\n")
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        data = json.dumps(
            {"path": self.path, "method": self.command, "body": body.decode()}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = respond
    do_POST = respond

    def log_message(self, *_):
        pass


def test_management_deep_links_keep_authentication_and_api_requests_on_the_backend(
    tmp_path,
):
    binary = os.environ.get("KOINON_TEST_NGINX") or shutil.which("nginx")
    if not binary:
        if os.environ.get("KOINON_REQUIRE_NGINX") == "1":
            pytest.fail("Native nginx is required for management proxy qualification")
        pytest.skip("Native nginx is not installed; the dedicated CI gate requires it")
    frontend = tmp_path / "frontend"
    (frontend / "assets").mkdir(parents=True)
    (frontend / "index.html").write_text(
        "<!doctype html><title>Owned management fixture</title>"
    )
    assets = {
        "brand.svg": ("<svg/>", "image/svg+xml"),
        "main.js": ("export {};", "text/javascript"),
        "main.css": ("body {}", "text/css"),
        "manrope.woff2": ("fixture", "font/woff2"),
    }
    for name, (content, _) in assets.items():
        (frontend / "assets" / name).write_text(content)
        (frontend / name).write_text(content)
    template = (
        Path(__file__).parents[1] / "production" / "nginx-management.conf"
    ).read_text()
    ApiFixture.stream_release.clear()
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), ApiFixture)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    template = template.replace(
        "/opt/koinon/current/frontend/dist/management/browser", str(frontend)
    )
    template = template.replace("127.0.0.1:18781", f"127.0.0.1:{upstream.server_port}")
    paths = "\n".join(
        f"{name}_temp_path {tmp_path / name};"
        for name in ("client_body", "proxy", "fastcgi", "uwsgi", "scgi")
    )
    config = tmp_path / "nginx.conf"
    config.write_text(
        f"daemon off; master_process off; pid {tmp_path / 'nginx.pid'};\n"
        f"error_log stderr warn; events {{ worker_connections 32; }}\n"
        f"http {{ access_log off; {paths}\n"
        f"server {{ listen 127.0.0.1:{port}; server_name localhost; {template} }} }}\n"
    )
    process = subprocess.Popen(
        [binary, "-p", str(tmp_path), "-c", str(config)], stderr=subprocess.PIPE
    )

    def request(path, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read(65537)
        finally:
            connection.close()

    try:
        deadline = time.monotonic() + 10
        while True:
            if process.poll() is not None:
                pytest.fail(
                    "Native nginx did not start: " + process.stderr.read().decode()
                )
            try:
                request("/")
                break
            except (ConnectionError, OSError):
                assert time.monotonic() < deadline, "Native nginx did not become ready"
                time.sleep(0.05)
        for path in (
            "/",
            "/chat",
            "/activity",
            "/settings",
            "/account/profile",
            "/account/tokens",
            "/account/applications?fixture=1",
        ):
            status, headers, body = request(path)
            assert status == 200 and b"Owned management fixture" in body
            assert headers["Cache-Control"] == "no-store"
            assert headers["X-Content-Type-Options"] == "nosniff"
        for path in (
            "/api/v1/authorized-applications?page=2",
            "/bff/api/v1/authorized-applications",
            "/oauth2/mcp/authorize",
            "/oauth2/mcp/token",
            "/login/oauth2/code/koinon",
            "/auth/me",
            "/auth/logout",
            "/logout",
            "/mcp",
            "/.well-known/oauth-protected-resource/mcp",
            "/health",
            "/ready",
        ):
            method = (
                "POST"
                if path in {"/oauth2/mcp/token", "/auth/logout", "/logout", "/mcp"}
                else "GET"
            )
            payload = "owned-fixture" if method == "POST" else None
            status, headers, body = request(path, method, payload)
            assert status == 200 and headers["Content-Type"] == "application/json"
            assert json.loads(body) == {
                "path": path,
                "method": method,
                "body": payload or "",
            }
        for name, (_, media_type) in assets.items():
            for prefix in ("/", "/assets/"):
                status, headers, _ = request(prefix + name)
                assert status == 200 and headers["Content-Type"].split(";")[0] == media_type
        assert request("/assets/missing.svg")[0] == 404
        for path in ("/missing.js", "/missing.css", "/missing.woff2"):
            assert request(path)[0] == 404
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", "/api/v1/stream-fixture")
            response = connection.getresponse()
            assert response.readline() == b"data: first\n"
            assert not ApiFixture.stream_release.is_set()
            ApiFixture.stream_release.set()
            assert b"data: done" in response.read(65537)
        finally:
            connection.close()
    finally:
        ApiFixture.stream_release.set()
        process.terminate()
        process.wait(timeout=5)
        if process.stderr:
            process.stderr.close()
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=2)

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace


def test_product_launcher_delegates_validated_properties_and_explicit_ports(monkeypatch, tmp_path):
    from koinon import serve

    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("synthetic certificate")
    key.write_text("synthetic key")
    monkeypatch.delenv("_PYFLY_SERVER_HOST", raising=False)
    monkeypatch.delenv("_PYFLY_SERVER_PORT", raising=False)
    monkeypatch.setattr(
        serve,
        "environment_configuration",
        lambda: {
            "pyfly": {
                "server": {
                    "host": "127.0.0.1",
                    "port": 18881,
                    "event_loop": "asyncio",
                    "http": "h2",
                    "graceful_timeout": 45,
                    "ssl_certfile": str(cert),
                    "ssl_keyfile": str(key),
                    "granian": {"runtime_threads": 3},
                }
            },
        },
    )
    calls = []
    monkeypatch.setattr(
        serve, "launch", lambda app, properties, **ports: calls.append((app, properties, ports))
    )
    server, loop = SimpleNamespace(), SimpleNamespace()
    serve.main(server=server, event_loop=loop)
    assert len(calls) == 1
    app, properties, ports = calls[0]
    assert app == "koinon.main:app"
    assert (properties.host, properties.port) == ("127.0.0.1", 18881)
    assert properties.graceful_timeout == 45 and properties.http == "h2"
    assert properties.ssl_certfile == str(cert) and properties.ssl_keyfile == str(key)
    assert properties.granian.runtime_threads == 3
    assert ports == {"server": server, "event_loop": loop}

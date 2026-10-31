# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Child fixtures can reach only their explicit private test sockets."""

import socket
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def restrict_owned_sockets(database_url: str, blob_endpoint: str | None = None) -> None:
    parsed = urlsplit(database_url)
    query = parse_qs(parsed.query)
    directory = Path(query["host"][0])
    if not str(directory).startswith("/tmp/koinon-bulk-pg-") or directory.stat().st_mode & 0o077:
        raise ValueError("An owner-only isolated PostgreSQL fixture is required")
    unix = str(directory / (".s.PGSQL." + query["port"][0]))
    loopback = None
    if blob_endpoint:
        blob = urlsplit(blob_endpoint)
        if blob.scheme != "http" or blob.hostname != "127.0.0.1" or not blob.port:
            raise ValueError("Only an explicit loopback Blob emulator is permitted")
        loopback = ("127.0.0.1", blob.port)
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex

    def allowed(connection, address):
        return (
            connection.family == socket.AF_UNIX
            and address == unix
            or connection.family == socket.AF_INET
            and loopback is not None
            and address == loopback
        )

    def connect(connection, address):
        if not allowed(connection, address):
            raise AssertionError("Bulk process fixture forbids other sockets")
        return original_connect(connection, address)

    def connect_ex(connection, address):
        if not allowed(connection, address):
            raise AssertionError("Bulk process fixture forbids other sockets")
        return original_connect_ex(connection, address)

    def denied(*args, **kwargs):
        raise AssertionError("Bulk process fixture forbids datagrams")

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.socket.sendto = denied

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent application/reader process, restricted to its synthetic PostgreSQL endpoint."""

import asyncio
import json
import os
import socket
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path

import psutil
from bulk_process_fixture import context_for
from sqlalchemy.engine import make_url


def restrict_database(uri):
    url = make_url(uri)
    if url.host != "127.0.0.1" or url.port == 18783 or not url.database.startswith("pinned_bulk_"):
        raise ValueError("Only a newly allocated, explicitly owned loopback database is allowed")
    endpoint = (url.host, url.port)
    connect, connect_ex = socket.socket.connect, socket.socket.connect_ex

    def allowed(connection, address):
        if connection.family != socket.AF_INET or address != endpoint:
            raise AssertionError("Parallel fixture forbids every other network endpoint")

    def guarded_connect(connection, address):
        allowed(connection, address)
        return connect(connection, address)

    def guarded_connect_ex(connection, address):
        allowed(connection, address)
        return connect_ex(connection, address)

    socket.socket.connect = guarded_connect
    socket.socket.connect_ex = guarded_connect_ex


def emit(event, **values):
    print(json.dumps({"event": event, **values}), flush=True)


async def main(path):
    values = json.loads(Path(path).read_text())
    restrict_database(values["url"])
    from flycanon.core.services.ingestion.file_parser import DocumentFilePolicy, parse_document_file

    from koinon.knowledge.bulk.queue import BulkQueue
    from koinon.knowledge.bulk.service import FileBatches
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    context = context_for(
        values["url"], values["root"], {"max_workers_global": 2, "max_workers_per_tenant": 2}
    )
    await context.start()
    admission = WorkAdmission(WorkAdmissionSettings(worker_capacity=1))
    try:
        async with admission.hold("bulk"):
            queue = context.get_bean(BulkQueue)
            service = context.get_bean(FileBatches)
            lease = await queue.claim(values["worker"])
            if lease is None:
                emit("empty")
                return
            emit(
                "claimed",
                pid=os.getpid(),
                item=lease.item_id,
                batch=lease.batch_id,
                subject=lease.subject,
                attempt=lease.attempt,
                active=admission.worker_active,
            )
            while command := await asyncio.to_thread(sys.stdin.readline):
                if command.strip() == "exit":
                    return
                if command.strip() != "parse":
                    raise ValueError("Unknown qualification command")
                peak = 0
                completed = asyncio.Event()
                child_observations = []

                async def observe(stop, observations):
                    nonlocal peak
                    process = psutil.Process()
                    while not stop.is_set():
                        rss = 0
                        children = process.children(recursive=True)
                        if children:
                            observations.append(time.monotonic())
                        for child in (process, *children):
                            with suppress(psutil.NoSuchProcess):
                                rss += child.memory_info().rss
                        peak = max(peak, rss)
                        await asyncio.sleep(0.02)

                monitor = asyncio.create_task(observe(completed, child_observations))
                try:
                    original = await queue.original(lease)
                    receipt = await service.receipt(
                        lease.subject, lease.tenant_id, lease.batch_id, lease.item_id
                    )
                    with tempfile.TemporaryDirectory(prefix="parallel-office-") as directory:
                        source = Path(directory) / "original"
                        await service.storage.read_file(original, source)
                        started = time.monotonic()
                        parsed = await parse_document_file(
                            source, filename=lease.filename, policy=DocumentFilePolicy()
                        )
                        finished = time.monotonic()
                        assert "Parallel qualification" in parsed.text
                    await queue.check(lease)
                    emit(
                        "parsed",
                        item=lease.item_id,
                        source=lease.source_id,
                        receipt=receipt.receipt_id,
                        sha256=receipt.sha256,
                        start=started,
                        end=finished,
                        parser_child_start=min(child_observations),
                        parser_child_end=max(child_observations),
                        peak_rss=peak,
                        active=admission.worker_active,
                    )
                except Exception as error:
                    emit("fenced", item=lease.item_id, code=getattr(error, "code", type(error).__name__))
                finally:
                    completed.set()
                    await monitor
    finally:
        await context.stop()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))

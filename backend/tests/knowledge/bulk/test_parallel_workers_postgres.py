# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Two processes admit and parse separate originals; this is not provider throughput proof."""

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack, suppress
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import psutil
import pytest
from test_bulk_native import bulk as bulk
from test_bulk_native import request
from test_bulk_pinned_postgres import bulk_schema_migrated as bulk_schema_migrated
from test_bulk_pinned_postgres import bulk_url as bulk_url

from koinon.catalog.entities import Membership
from koinon.knowledge.bulk.dtos import BulkAction

pytestmark = pytest.mark.integration


class Worker:
    def __init__(self, process):
        self.process = process

    async def message(self):
        async with asyncio.timeout(45):
            while line := await self.process.stdout.readline():
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict) and "event" in value:
                    return value
        error = await self.process.stderr.read()
        raise AssertionError(error.decode()[-2000:])

    async def command(self, command):
        self.process.stdin.write((command + "\n").encode())
        await self.process.stdin.drain()

    async def close(self):
        try:
            if self.process.returncode is None:
                await self.command("exit")
            await asyncio.wait_for(self.process.wait(), 15)
        except (TimeoutError, BrokenPipeError, ConnectionResetError):
            if self.process.returncode is None:
                parent = psutil.Process(self.process.pid)
                for child in parent.children(recursive=True):
                    with suppress(psutil.NoSuchProcess):
                        child.kill()
                self.process.kill()
                await self.process.wait()


async def start_worker(stack, tmp_path, bulk, url):
    path = tmp_path / (uuid4().hex + ".json")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump({"url": url, "root": bulk.service.settings.storage_root, "worker": uuid4().hex}, output)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path(__file__).parent) + os.pathsep + environment.get("PYTHONPATH", "")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("parallel_worker_fixture.py")),
        str(path),
        env=environment,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    worker = Worker(process)
    stack.push_async_callback(worker.close)
    return worker, await worker.message()


async def stage_items(bulk, same_batch):
    from docx import Document

    output = BytesIO()
    document = Document()
    for index in range(300):
        document.add_paragraph(f"Parallel qualification paragraph {index} preserves the original.")
    document.save(output)
    content = output.getvalue()
    await bulk.members.save(Membership(id="other", subject="issuer|other", tenant_id="north", role="editor"))
    receipts = {}
    for ordinal in range(1 if same_batch else 3):
        subject = "issuer|other" if ordinal == 1 else "issuer|editor"
        manifest = request(bulk.target, content)
        manifest = manifest.model_copy(
            update={
                "items": [
                    manifest.items[0].model_copy(
                        update={
                            "filename": f"parallel-{item}.docx",
                            "client_item_id": str(item),
                        }
                    )
                    for item in range(3 if same_batch else 1)
                ],
            }
        )
        batch = await bulk.service.create(subject, "north", manifest, "parallel-" + str(ordinal))
        for item in (await bulk.service.items(subject, "north", batch.id)).items:
            receipt = await bulk.service.stage(
                subject, "north", batch.id, item.id, content, "upload-" + item.id
            )
            receipts[item.id] = receipt
        current = await bulk.service.get(subject, "north", batch.id)
        await bulk.service.submit(
            subject, "north", batch.id, BulkAction(expected_revision=current.revision), "submit"
        )
    return receipts


async def item_states(bulk, receipts):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.repositories import BulkRepository

    async with infrastructure_unit(bulk.context.get_bean(DataSourceRegistry).primary):
        records = bulk.context.get_bean(BulkRepository)
        result = {}
        for identifier, receipt in receipts.items():
            item = await records.item(receipt.batch_id, identifier)
            job = await records.job(item.job_id)
            result[identifier] = (item.status, job.attempts)
        return result


@pytest.mark.parametrize("same_batch", [True, False])
async def test_two_processes_parse_in_parallel_and_a_third_cannot_claim(bulk, bulk_url, tmp_path, same_batch):
    receipts = await stage_items(bulk, same_batch)
    async with AsyncExitStack() as stack:
        first, second = await asyncio.gather(
            start_worker(stack, tmp_path, bulk, bulk_url), start_worker(stack, tmp_path, bulk, bulk_url)
        )
        workers, claims = zip(first, second, strict=True)
        assert all(claim["event"] == "claimed" and claim["active"] == 1 for claim in claims)
        assert len({claim["item"] for claim in claims}) == 2
        assert len({claim["pid"] for claim in claims}) == 2
        assert len({claim["batch"] for claim in claims}) == (1 if same_batch else 2)
        if not same_batch:
            assert {claim["subject"] for claim in claims} == {"issuer|editor", "issuer|other"}
        _, third = await start_worker(stack, tmp_path, bulk, bulk_url)
        assert third == {"event": "empty"}
        assert sorted((await item_states(bulk, receipts)).values()) == [
            ("queued", 0),
            ("running", 1),
            ("running", 1),
        ]
        await asyncio.gather(*(worker.command("parse") for worker in workers))
        outcomes = await asyncio.gather(*(worker.message() for worker in workers))
        assert all(outcome["event"] == "parsed" and outcome["active"] == 1 for outcome in outcomes)
        assert max(row["start"] for row in outcomes) < min(row["end"] for row in outcomes)
        assert max(row["parser_child_start"] for row in outcomes) < min(
            row["parser_child_end"] for row in outcomes
        )
        assert all(0 < row["peak_rss"] < 2 * 1024**3 for row in outcomes)
        assert len({row["source"] for row in outcomes}) == len({row["receipt"] for row in outcomes}) == 2
        for row in outcomes:
            assert row["receipt"] == receipts[row["item"]].receipt_id
            assert row["sha256"] == receipts[row["item"]].sha256
        assert sorted((await item_states(bulk, receipts)).values()) == [
            ("queued", 0),
            ("running", 1),
            ("running", 1),
        ]
        print(json.dumps({"same_batch": same_batch, "parallel_reader_proof": outcomes}))


async def test_cancelling_one_batch_fences_only_its_process_without_replaying_other_work(
    bulk, bulk_url, tmp_path
):
    receipts = await stage_items(bulk, same_batch=False)
    async with AsyncExitStack() as stack:
        first, second = await asyncio.gather(
            start_worker(stack, tmp_path, bulk, bulk_url), start_worker(stack, tmp_path, bulk, bulk_url)
        )
        first_worker, first_claim = first
        second_worker, second_claim = second
        assert first_claim["batch"] != second_claim["batch"]
        await second_worker.command("parse")
        batch = await bulk.service.get(first_claim["subject"], "north", first_claim["batch"])
        cancelled = await bulk.service.cancel(
            first_claim["subject"], "north", batch.id, BulkAction(expected_revision=batch.revision), "cancel"
        )
        assert cancelled.status == "cancelled"
        await first_worker.command("parse")
        stopped, completed = await asyncio.gather(first_worker.message(), second_worker.message())
        assert stopped == {"event": "fenced", "item": first_claim["item"], "code": "BULK_LEASE_LOST"}
        assert completed["event"] == "parsed" and completed["item"] == second_claim["item"]
        assert completed["receipt"] == receipts[completed["item"]].receipt_id
        _, next_claim = await start_worker(stack, tmp_path, bulk, bulk_url)
        assert next_claim["event"] == "claimed" and next_claim["attempt"] == 1
        assert next_claim["item"] not in {first_claim["item"], second_claim["item"]}
        assert (await item_states(bulk, receipts)) == {
            first_claim["item"]: ("cancelled", 1),
            second_claim["item"]: ("running", 1),
            next_claim["item"]: ("running", 1),
        }

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Measure native selected-metadata construction, not a complete RLM answer."""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
import platform
import resource
import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder, Filters
from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.interfaces.dtos.rlm_corpus import SourceMeta
from flycanon.models.entities.source import SourceRow
from flycanon.models.repositories.knowledge_repository import KnowledgeRepository
from flycanon.models.repositories.source_repository import SourceRepository
from sqlalchemy import Table, event, insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class ObservedObjectStore(LocalFsObjectStore):
    reads = 0

    async def get(self, key: str) -> bytes:
        self.reads += 1
        return await super().get(key)

    def get_sync(self, key: str) -> bytes:
        self.reads += 1
        return super().get_sync(key)

    async def get_bounded(self, key: str, max_bytes: int) -> bytes:
        self.reads += 1
        return await super().get_bounded(key, max_bytes)


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


async def measure(selected: int, stored: int, scratch: Path, *, analyze: bool = False) -> dict:
    if not 1 <= selected <= stored <= 100_000:
        raise ValueError("Require 1 <= selected <= stored <= 100000 for this local probe")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = SourceRepository(factory, engine=engine)
    object_store = ObservedObjectStore(str(scratch))
    statements: list[str] = []
    first_query: list[tuple] = []

    def observed(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)
        if not first_query:
            first_query.append((statement, _parameters))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(cast(Table, SourceRow.__table__).create)
            for start in range(0, stored, 200):
                rows = [
                    {
                        "id": f"source-{number:08d}",
                        "tenant_id": "probe-tenant",
                        "workspace_id": "probe-workspace",
                        "kind": "markdown",
                        "status": "ingested",
                        "filename": "report.md",
                        "content_sha256": hashlib.sha256(str(number).encode()).hexdigest(),
                        "object_store_key": f"originals/{number}.md",
                        "metadata_json": {"tags": ["study"]},
                        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
                    }
                    for number in range(start, min(stored, start + 200))
                ]
                await connection.execute(insert(SourceRow), rows)
            for identifier, tenant, workspace, status in (
                ("foreign-tenant", "other", "probe-workspace", "ingested"),
                ("foreign-workspace", "probe-tenant", "other", "ingested"),
                ("pending", "probe-tenant", "probe-workspace", "pending"),
            ):
                await connection.execute(insert(SourceRow), {
                    "id": identifier, "tenant_id": tenant, "workspace_id": workspace,
                    "kind": "markdown", "status": status, "filename": "excluded.md",
                    "content_sha256": hashlib.sha256(identifier.encode()).hexdigest(),
                })
            if analyze:
                await connection.exec_driver_sql("ANALYZE")
        denied = await repository.get_many_scoped(
            ["foreign-tenant", "foreign-workspace", "pending"],
            tenant_id="probe-tenant", workspace_id="probe-workspace", statuses=["ingested"],
        )
        if denied:
            raise RuntimeError("Scoped repository admitted an excluded fixture row")
        identifiers = [f"source-{number:08d}" for number in range(selected)]
        builder = CanonCorpusBuilder(
            source_repository=repository,
            knowledge_repository=KnowledgeRepository(factory, engine=engine),
            object_store=object_store,
        )
        gc.collect()
        before_rss = peak_rss_bytes()
        event.listen(engine.sync_engine, "before_cursor_execute", observed)
        started, cpu_started = time.perf_counter(), time.process_time()
        corpus = await builder.build(
            tenant_id="probe-tenant", workspace_id="probe-workspace",
            filters=Filters(source_ids=identifiers, statuses=["ingested"], tags=["study"]),
        )
        elapsed, cpu = time.perf_counter() - started, time.process_time() - cpu_started
        after_rss = peak_rss_bytes()
        event.remove(engine.sync_engine, "before_cursor_execute", observed)
        keys = list(corpus)
        returned = set()
        for key in keys:
            metadata = corpus.resolve(key)
            if not isinstance(metadata, SourceMeta):
                raise TypeError("Metadata probe received an unexpected source type")
            returned.add(metadata.source_id)
        if returned != set(identifiers) or len(keys) != selected:
            raise RuntimeError("Metadata probe lost or widened selected scope")
        if object_store.reads or len(statements) != math.ceil(selected / 200):
            raise RuntimeError("Unexpected content I/O or selected metadata SQL growth")
        statement, parameters = first_query[0]
        async with engine.connect() as connection:
            plan = await connection.exec_driver_sql("EXPLAIN QUERY PLAN " + statement, parameters)
            plan_details = [str(row[-1]) for row in plan]
        return {
            "selected_sources": selected, "stored_sources": stored + 3,
            "returned_sources": len(returned), "unexpected_scope_rows": len(denied),
            "duplicate_filename_keys": len(keys), "sql_statements": len(statements),
            "elapsed_seconds": elapsed, "process_cpu_seconds": cpu,
            "process_lifetime_peak_rss_before_bytes": before_rss,
            "process_lifetime_peak_rss_bytes": after_rss,
            "object_reads": object_store.reads, "provider_calls": 0,
            "first_batch_query_plan": plan_details,
            "statistics": (
                "ANALYZE completed before timed phase" if analyze else "fresh fixture without ANALYZE"
            ),
            "measurement": "selected_metadata_only_without_version_pins_or_authorization",
        }
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--stored", type=int, help="Fixed catalog size, otherwise twice selection")
    parser.add_argument("--analyze", action="store_true", help="Update SQLite statistics before timing")
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 20 or any(
        not 1 <= size <= (args.stored or size * 2) <= 100_000 for size in args.sizes
    ):
        parser.error("Invalid size/repeat range; see module documentation")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error("Output already exists; retain it and choose a new path")
    if args.child:
        result = asyncio.run(measure(
            args.sizes[0], args.stored, args.output.with_suffix(".objects"), analyze=args.analyze,
        ))
    else:
        rows = []
        for size in args.sizes:
            for number in range(args.repeats):
                child = args.output.with_name(f"{args.output.stem}-{size}-{number}.json")
                subprocess.run([
                    sys.executable, "-B", str(Path(__file__).resolve()), "--child",
                    "--sizes", str(size), "--stored", str(args.stored or size * 2),
                    "--output", str(child),
                    *(["--analyze"] if args.analyze else []),
                ], check=True, timeout=180)
                rows.append(json.loads(child.read_text()))
        implementation = {
            name: hashlib.sha256(Path(inspect.getfile(implementation)).read_bytes()).hexdigest()
            for name, implementation in (
                ("corpus_builder", CanonCorpusBuilder), ("source_repository", SourceRepository)
            )
        }
        result = {
            "schema_version": 1, "recorded_at": datetime.now(UTC).isoformat(),
            "python": platform.python_version(), "os": platform.system(),
            "os_version": platform.release(), "machine": platform.machine(),
            "logical_cpus": os.cpu_count(), "sqlite": sqlite3.sqlite_version,
            "pyfly": importlib.metadata.version("pyfly"),
            "source_sha256": implementation,
            "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "isolation": "one subprocess and one in-memory SQLite database per sample",
            "rss_scope": "process lifetime including imports and fixture setup; not per-stage allocation",
            "cache_state": "fresh process; fixture insertion warms SQLite; OS caches uncontrolled",
            "excluded": ["product_permissions", "version_pins", "document_content", "model", "network"],
            "samples": rows,
        }
    with args.output.open("x") as destination:
        json.dump(result, destination, indent=2, allow_nan=False)
        destination.write("\n")


if __name__ == "__main__":
    main()

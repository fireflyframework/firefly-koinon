# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Run one bounded maintenance batch; output identifiers and classifications only."""

import argparse
import asyncio
import json
import os
from dataclasses import asdict

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from koinon.answers.release_backfill import AnswerReleaseBackfill


def connection_url(value):
    try:
        url = make_url(value)
    except Exception:
        raise ValueError("Configure the dedicated answer maintenance connection") from None
    if url.get_backend_name() != "postgresql" or not url.username or not url.database:
        raise ValueError("Configure a PostgreSQL maintenance identity and database")
    if url.username in {"postgres", "koinon_catalog", "koinon_answer_publisher", "koinon_migrator"}:
        raise ValueError("Use an isolated maintenance identity")
    return url.set(drivername="postgresql+asyncpg")


async def execute(args):
    url = connection_url(os.environ.get("KOINON_ANSWER_MAINTENANCE_DATABASE_URL", ""))
    engine = create_async_engine(
        url, pool_size=1, max_overflow=0, pool_timeout=1, echo=False, hide_parameters=True
    )
    try:
        runner = AnswerReleaseBackfill.for_database(
            async_sessionmaker(engine), url.username, audit=args.audit
        )
        # Distinct journals prevent a write-backfill checkpoint from masquerading as a completed audit.
        job_id = ("audit:" if args.audit else "backfill:") + args.job
        report = await runner.run(job_id, tenant_id=args.tenant)
        return {**asdict(report), "mode": "audit" if args.audit else "backfill", "endpoint_enabled": False}
    finally:
        await engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, help="Stable resume identity, at most 55 characters")
    parser.add_argument("--tenant", help="Optional immutable tenant scope")
    parser.add_argument(
        "--audit", action="store_true", help="Re-verify without creating proofs; use a new job after backfill"
    )
    args = parser.parse_args(argv)
    if not 1 <= len(args.job) <= 55 or args.tenant is not None and not 1 <= len(args.tenant) <= 64:
        parser.error("Use bounded job and tenant identifiers")
    try:
        result = asyncio.run(execute(args))
    except KeyboardInterrupt:
        print(json.dumps({"state": "interrupted", "retry": "resume the same job after its claim expires"}))
        return 130
    except Exception:
        # Driver exception strings may contain credentials, statement parameters or protected values.
        print(
            json.dumps(
                {"state": "unavailable", "retry": "check maintenance role, migrations and claim lease"}
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["state"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())

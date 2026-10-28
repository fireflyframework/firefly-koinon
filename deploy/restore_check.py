# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Restore into a newly named isolated database; never clean or overwrite a database."""

import argparse
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import psycopg
from backup import postgres_environment, postgres_tool
from psycopg import sql
from sqlalchemy.engine import make_url


def restore(archive: Path):
    if not archive.is_file():
        raise FileNotFoundError("Custom archive not found")
    url = make_url(os.environ["KOINON_MIGRATION_DATABASE_URL"])
    database = "koinon_restore_" + uuid4().hex[:16]
    environment = postgres_environment(url)
    source = url.set(drivername="postgresql")
    with psycopg.connect(
        source.set(database="postgres").render_as_string(hide_password=False),
        autocommit=True,
    ) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
        )
    subprocess.run(
        [
            postgres_tool("pg_restore"),
            "--host",
            url.host,
            "--port",
            str(url.port or 5432),
            "--username",
            url.username,
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--dbname",
            database,
            str(archive),
        ],
        env=environment,
        check=True,
    )
    with psycopg.connect(
        source.set(database=database).render_as_string(hide_password=False)
    ) as connection:
        heads = {}
        for name in ("native", "canon", "structured"):
            heads[name] = connection.execute(
                sql.SQL("SELECT version_num FROM {}").format(
                    sql.Identifier(f"koinon_{name}_version")
                )
            ).fetchall()
        tenants = connection.execute("SELECT count(*) FROM lattice_tenants").fetchone()[
            0
        ]
    return {"database": database, "migration_heads": heads, "tenant_count": tenants}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    print(restore(parser.parse_args().archive))

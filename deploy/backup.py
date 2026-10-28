# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Create a private PostgreSQL custom archive; credentials never enter command arguments."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url


def postgres_environment(url):
    result = os.environ.copy()
    result["PGPASSWORD"] = url.password or ""
    names = {
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
        "sslcrl": "PGSSLCRL",
        "channel_binding": "PGCHANNELBINDING",
        "connect_timeout": "PGCONNECT_TIMEOUT",
        "target_session_attrs": "PGTARGETSESSIONATTRS",
        "options": "PGOPTIONS",
    }
    for key, value in url.query.items():
        if key not in names or not isinstance(value, str):
            raise ValueError(
                "Unsupported PostgreSQL tool URL option; refusing to omit it"
            )
        result[names[key]] = value
    return result


def postgres_tool(name):
    folder = os.environ.get("KOINON_POSTGRES_BIN")
    selected = str(Path(folder) / name) if folder else shutil.which(name)
    if not selected:
        raise RuntimeError(
            f"Configure PostgreSQL17 {name} on PATH or KOINON_POSTGRES_BIN"
        )
    return selected


def backup(output: Path):
    if output.exists():
        raise FileExistsError("Backup target already exists; choose a new file")
    url = make_url(os.environ["KOINON_MIGRATION_DATABASE_URL"])
    environment = postgres_environment(url)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    subprocess.run(
        [
            postgres_tool("pg_dump"),
            "--host",
            url.host,
            "--port",
            str(url.port or 5432),
            "--username",
            url.username,
            "--format=custom",
            "--file",
            str(output),
            url.database,
        ],
        env=environment,
        check=True,
    )
    output.chmod(0o600)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    print("Private custom archive created:", backup(parser.parse_args().output))

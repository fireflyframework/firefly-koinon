# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Upgrade native and knowledge histories without merging their revision identities."""

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
HISTORIES = (
    ("native", ROOT / "deploy/migrations/native_versions"),
    ("canon", ROOT / "packages/canon/migrations/versions"),
    ("structured", ROOT / "packages/structured/migrations/versions"),
)


def history_config(name, versions, connection):
    config = Config()
    config.set_main_option("script_location", str(ROOT / "deploy/migrations"))
    locations = [versions]
    if name in {"canon", "structured"}:
        locations.append(versions.parent / "koinon_versions")
    config.set_main_option("version_locations", os.pathsep.join(map(str, locations)))
    config.set_main_option("path_separator", "os")
    config.set_main_option("version_path_separator", "os")
    config.attributes.update(connection=connection, version_table=f"koinon_{name}_version")
    return config


def migrate(url: str, *, check: bool = False) -> dict:
    target = make_url(url).set(drivername="postgresql+psycopg")
    engine = create_engine(target, pool_pre_ping=True)
    results = {}
    try:
        with engine.connect() as connection:
            if not check:
                if "alembic_version" in inspect(connection).get_table_names():
                    raise RuntimeError(
                        "An original unqualified Alembic history exists; review its mapping first"
                    )
                connection.execute(text("SET lock_timeout = '30s'"))
                connection.execute(text("SELECT pg_advisory_lock(hashtext('koinon-schema-migrations'))"))
                connection.commit()
            try:
                for name, versions in HISTORIES:
                    config = history_config(name, versions, connection)
                    expected = set(ScriptDirectory.from_config(config).get_heads())
                    if not check:
                        command.upgrade(config, "heads")
                        connection.commit()
                    actual = set(
                        MigrationContext.configure(
                            connection, opts={"version_table": f"koinon_{name}_version"}
                        ).get_current_heads()
                    )
                    if actual != expected:
                        raise RuntimeError(f"{name} migration revision is not current")
                    results[name] = sorted(actual)
            finally:
                if not check:
                    connection.rollback()
                    connection.execute(
                        text("SELECT pg_advisory_unlock(hashtext('koinon-schema-migrations'))")
                    )
                    connection.commit()
    finally:
        engine.dispose()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Read revisions without applying migrations",
    )
    args = parser.parse_args()
    url = os.environ.get("KOINON_MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Set KOINON_MIGRATION_DATABASE_URL to the migration role; runtime credentials are separate"
        )
    for name, revisions in migrate(url, check=args.check).items():
        print(f"{name}: {', '.join(revisions)}")


if __name__ == "__main__":
    main()

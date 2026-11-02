# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_upgrade_preserves_existing_locale_timezone_and_explicit_defaults():
    path = Path(__file__).parents[3] / "deploy/migrations/native_versions/0042_profile_preferences.py"
    spec = importlib.util.spec_from_file_location("profile_preferences_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE koinon_profiles (id TEXT PRIMARY KEY, locale TEXT, time_zone TEXT)"
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_profiles VALUES ('old-default', 'en-US', 'UTC'), "
            "('old-custom', 'es-MX', 'America/Mexico_City')"
        )
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            migration.upgrade()
        assert connection.exec_driver_sql("SELECT * FROM koinon_profiles ORDER BY id").all() == [
            ("old-custom", "es-MX", "America/Mexico_City", 1),
            ("old-default", "en-US", "UTC", 1),
        ]
    engine.dispose()

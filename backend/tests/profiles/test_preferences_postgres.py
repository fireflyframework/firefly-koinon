# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Qualify the additive migration and concurrent initialization on an owned PostgreSQL database."""

import asyncio
import importlib.util
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
import test_profiles as fixtures
from alembic.migration import MigrationContext
from alembic.operations import Operations
from psycopg import sql
from sqlalchemy.engine import make_url

from koinon.profiles.entities import Profile
from koinon.profiles.service import profile_id


@pytest.mark.integration
async def test_postgres_upgrade_preserves_preferences_and_serializes_device_defaults(tmp_path, monkeypatch):
    configured = os.getenv("KOINON_PROFILE_PREFERENCES_TEST_PG_URL")
    if not configured:
        pytest.skip("Set KOINON_PROFILE_PREFERENCES_TEST_PG_URL for an owned PostgreSQL test database")
    url = make_url(configured)
    database = "profile_preferences_" + uuid4().hex
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    target = url.set(drivername="postgresql+psycopg", database=database)
    (tmp_path / "owned-database.txt").write_text(database + "\n")
    engine = sa.create_engine(target)
    metadata = sa.MetaData()
    previous = sa.Table(
        "koinon_profiles",
        metadata,
        *(
            sa.Column(
                column.name,
                column.type,
                primary_key=column.primary_key,
                nullable=column.nullable,
                unique=column.unique,
            )
            for column in Profile.__table__.columns
            if column.name != "preferences_initialized"
        ),
    )
    spec = importlib.util.spec_from_file_location(
        "preferences42",
        Path(__file__).parents[3] / "deploy/migrations/native_versions/0042_profile_preferences.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(
                previous.insert().values(
                    id=profile_id("issuer|existing"),
                    subject="issuer|existing",
                    display_name="Existing",
                    locale="en-US",
                    time_zone="UTC",
                    response_language="auto",
                    updated_at=datetime.now(UTC),
                )
            )
            with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
                migration.upgrade()
            assert connection.exec_driver_sql(
                "SELECT locale,time_zone,preferences_initialized FROM koinon_profiles "
                "WHERE subject='issuer|existing'"
            ).one() == ("en-US", "UTC", True)
            assert [
                column["name"] for column in sa.inspect(connection).get_columns("koinon_profiles")
            ] == list(Profile.__table__.c.keys())
        real_config = fixtures.Config

        def configuration(values):
            values["pyfly"]["data"]["relational"]["url"] = target.render_as_string(hide_password=False)
            return real_config(values)

        monkeypatch.setattr(fixtures, "Config", configuration)
        generator = fixtures.profiles.__wrapped__(tmp_path)
        service, _ = await anext(generator)
        try:
            preserved = await service.update("issuer|existing", {"locale": "es-ES"}, initialize_only=True)
            assert preserved["locale"] == "en-US" and preserved["time_zone"] == "UTC"
            first, second = await asyncio.gather(
                service.update(
                    "issuer|member", {"locale": "es-ES", "time_zone": "Europe/Madrid"}, initialize_only=True
                ),
                service.update(
                    "issuer|member", {"locale": "en-GB", "time_zone": "Europe/London"}, initialize_only=True
                ),
            )
            assert first == second and first["preferences_initialized"] is True
            await service.update("issuer|member", {"locale": "es-MX-u-ca-gregory-hc-h23"})
            later = await service.update("issuer|member", {"locale": "en-US"}, initialize_only=True)
            assert later["locale"] == "es-MX-u-ca-gregory-hc-h23"
        finally:
            await generator.aclose()
    finally:
        engine.dispose()
    # Retain the owned database for review; never drop a caller-supplied database.

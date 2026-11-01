# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest
from pyfly.data.relational.sqlalchemy import Base
from sqlalchemy import create_engine, delete, update
from sqlalchemy.exc import IntegrityError

from koinon.catalog.entities import Tenant
from koinon.communications.entities import InstallationRecord
from koinon.installation.entities import InstallationRun


@pytest.fixture
def ledger(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'guards.db'}")
    Base.metadata.create_all(
        engine, tables=[Tenant.__table__, InstallationRecord.__table__, InstallationRun.__table__]
    )
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(Tenant.__table__.insert().values(id="example", name="Example"))
        connection.execute(
            InstallationRecord.__table__.insert().values(
                singleton="installation", installation_id="installation", created_at=now
            )
        )
        connection.execute(
            InstallationRun.__table__.insert().values(
                id="run",
                installation_id="installation",
                tenant_id="example",
                plan_key="initial",
                plan_sha256="a" * 64,
                status="completed",
                generation=1,
                checkpoints={"provider:chat": {"resource_id": "provider", "status": "done"}},
                created_at=now,
                updated_at=now,
            )
        )
    yield engine
    engine.dispose()


def test_completed_installation_cannot_be_reset_or_retargeted(ledger):
    for values in ({"plan_sha256": "b" * 64}, {"status": "partial"}, {"checkpoints": {}}):
        with pytest.raises(IntegrityError), ledger.begin() as connection:
            connection.execute(update(InstallationRun).where(InstallationRun.id == "run").values(**values))


def test_installation_receipts_cannot_be_deleted(ledger):
    with pytest.raises(IntegrityError), ledger.begin() as connection:
        connection.execute(delete(InstallationRun).where(InstallationRun.id == "run"))

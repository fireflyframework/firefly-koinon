# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Closed private account-operation contracts."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from pyfly.data.relational.sqlalchemy import Base

from koinon.catalog.entities import Tenant
from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationIdentity,
    AccountOperationLease,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operation_entities import ACCOUNT_OPERATION_TABLES


def test_account_metadata_creates_on_sqlite_for_service_tests():
    engine = sa.create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine, tables=[Tenant.__table__, *ACCOUNT_OPERATION_TABLES])
        with engine.connect() as connection:
            for table in ACCOUNT_OPERATION_TABLES:
                assert connection.execute(sa.select(table)).all() == []
    finally:
        engine.dispose()


def request(**changes):
    return AccountOperationRequest.model_validate(
        dict(
            kind="validation",
            operation_id="validation",
            revision=1,
            connection_id="connection",
            connection_revision=1,
            owner="owner",
            process_instance_id="worker",
            **changes,
        )
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"revision": -1},
        {"revision": True},
        {"generation": 1},
        {"connection_revision": -1},
        {"operation_id": ""},
        {"unknown": 1},
    ],
)
def test_invalid_operation_identity_is_rejected(changes):
    values = dict(
        kind="validation",
        operation_id="validation",
        revision=1,
        generation=0,
        connection_id="connection",
        connection_revision=1,
        owner="owner",
        process_instance_id="worker",
    )
    with pytest.raises(ValidationError):
        AccountOperationRequest.model_validate(values | changes)


def test_private_lease_requires_exact_digest_and_bounded_aware_deadline():
    with pytest.raises(ValidationError):
        AccountOperationIdentity(tenant_id="tenant", account_key=b"short")
    now = datetime.now(UTC)
    values = dict(
        identity=AccountOperationIdentity(tenant_id="tenant", account_key=b"a" * 32),
        operation=request(),
        token=uuid4(),
        fence=1,
        ticket=1,
        started_at=now,
        expires_at=now + timedelta(seconds=150),
    )
    lease = AccountOperationLease(**values)
    assert lease.expires_at - lease.started_at == timedelta(seconds=150)
    assert str(lease.token) not in repr(lease)
    for changes in (
        {"fence": 0},
        {"expires_at": now},
        {"expires_at": now + timedelta(seconds=151)},
        {"started_at": now.replace(tzinfo=None)},
    ):
        with pytest.raises(ValidationError):
            AccountOperationLease.model_validate(values | changes)


def test_busy_cannot_disclose_holder_or_unbounded_delay():
    assert AccountOperationBusy().retry_after_seconds == 1
    for values in ({"retry_after_seconds": 0}, {"retry_after_seconds": 31}, {"holder": "other"}):
        with pytest.raises(ValidationError):
            AccountOperationBusy.model_validate(values)

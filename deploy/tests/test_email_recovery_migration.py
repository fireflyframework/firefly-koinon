# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from koinon.communications.observation_entities import DeliveryBindingRecord, DeliveryInspectionRecord, DeliveryObservationRecord
from koinon.communications.recovery_entities import WelcomeRecoveryRecord

FILE=Path(__file__).parents[1]/"migrations/native_versions/0041_email_recovery.py"


def migration():
    spec=importlib.util.spec_from_file_location("email_recovery_migration41",FILE)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


def test_additive41_matches_native_models_and_keeps_existing_welcome_unchanged():
    value=migration()
    assert value.revision=="koinon_0041_email_recovery" and value.down_revision=="koinon_0040_bulk_pinned"
    engine=sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants(id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE koinon_communication_outbox(id TEXT PRIMARY KEY,status TEXT,attempt_count INTEGER)")
        connection.exec_driver_sql("CREATE TABLE koinon_operator_delivery_contacts(id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO koinon_communication_outbox VALUES('retained','unknown',1)")
        with Operations.context(MigrationContext.configure(connection)):value.upgrade()
        assert connection.exec_driver_sql("SELECT status,attempt_count FROM koinon_communication_outbox WHERE id='retained'").one()==("unknown",1)
        inspector=sa.inspect(connection)
        for model in (WelcomeRecoveryRecord,DeliveryBindingRecord,DeliveryInspectionRecord,DeliveryObservationRecord):
            table=model.__table__;actual={x['name']:x for x in inspector.get_columns(table.name)}
            assert set(actual)==set(table.c.keys())
            assert all(actual[c.name]['nullable']==c.nullable for c in table.c)
            assert {i['name'] for i in inspector.get_indexes(table.name)}=={i.name for i in table.indexes}
        connection.exec_driver_sql("INSERT INTO koinon_email_provider_bindings VALUES('retained','north','azure-communication-email',?,?, 'operator_historical',?,CURRENT_TIMESTAMP)",('a'*64,'00000000-0000-4000-8000-000000000001','b'*64))
        with pytest.raises(sa.exc.IntegrityError):connection.exec_driver_sql("UPDATE koinon_email_provider_bindings SET provider='changed'")
        with pytest.raises(sa.exc.IntegrityError):connection.exec_driver_sql("DELETE FROM koinon_email_provider_bindings")
    engine.dispose()

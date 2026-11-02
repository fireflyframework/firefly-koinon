# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.communications.observation_entities import (
    DeliveryBindingRecord,
    DeliveryInspectionRecord,
    DeliveryObservationRecord,
)


@repository(name="communications.email_provider_bindings")
class DeliveryBindingRepository(Repository[DeliveryBindingRecord, str]):
    pass


@repository(name="communications.email_operation_inspections")
class DeliveryInspectionRepository(Repository[DeliveryInspectionRecord, str]):
    pass


@repository(name="communications.email_operation_observations")
class DeliveryObservationRepository(Repository[DeliveryObservationRecord, str]):
    pass

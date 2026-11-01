# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.communications.contact_entities import OperatorContactRecord


@repository(name="communications.operator_contacts")
class OperatorContactRepository(Repository[OperatorContactRecord, str]):
    pass

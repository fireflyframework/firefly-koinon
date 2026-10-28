# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.knowledge.entities import DomainBinding


@repository(name="knowledge.bindings")
class DomainBindingRepository(Repository[DomainBinding, str]):
    """Explicit durable identities, never inferred from editable catalog metadata."""

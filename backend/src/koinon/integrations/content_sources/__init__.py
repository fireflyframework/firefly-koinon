# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only delegated sources; activation requires personal reader authorization."""

from pyfly.data.relational.sqlalchemy import Base
from sqlalchemy import event

from koinon.catalog import history_entities as _history_entities  # noqa: F401
from koinon.integrations.content_sources import publication_entities as _publication_entities  # noqa: F401
from koinon.integrations.content_sources.publication_guards import install_on_create

event.listen(Base.metadata, "after_create", install_on_create)

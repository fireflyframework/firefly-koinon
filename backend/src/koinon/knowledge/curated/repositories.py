# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository

from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot, KnowledgeIntentRow


@repository(name="knowledge.curated.intents")
class KnowledgeIntentRepository(Repository[KnowledgeIntentRow, str]):
    pass


@repository(name="knowledge.curated.catalog_state")
class CuratedCatalogStateRepository(Repository[CuratedCatalogState, str]):
    pass


@repository(name="knowledge.curated.source_roots")
class CuratedSourceRootRepository(Repository[CuratedSourceRoot, str]):
    pass

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from koinon.catalog.entities import CatalogEntry

SearchGroup = dict[str, tuple[CatalogEntry, CatalogEntry]]


@dataclass(frozen=True)
class SearchAdmission:
    assets: list[CatalogEntry]
    documents: dict[tuple[str, str], SearchGroup]
    curated: dict[tuple[str, str], SearchGroup]

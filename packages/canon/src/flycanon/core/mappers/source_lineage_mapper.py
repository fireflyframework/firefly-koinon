# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure immutable document record mappings."""

from math import ceil

from flycanon.core.services.sources.lineage.dtos import Admission, DocumentScope, LineagePage


def identity(scope: DocumentScope, source_id: str) -> dict[str, str]:
    return {"tenant_id": scope.tenant_id, "workspace_id": scope.workspace_id, "source_id": source_id}


def to_admission(version, artifact) -> Admission:
    return Admission(
        version["source_id"],
        version["id"],
        artifact["id"],
        artifact["sha256"],
        artifact["bytes"],
        artifact["object_key"],
        version["predecessor_id"],
        version["expected_extraction_id"],
    )


def to_lineage_page(rows, total: int, page: int, page_size: int) -> LineagePage:
    return LineagePage(tuple(dict(row) for row in rows), total, page, page_size, ceil(total / page_size))

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from flyquery.core.services.tables.table_service import TableService

from koinon.knowledge.adapters import NativeDomains
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


async def test_canonical_schema_retains_actual_native_sheet_or_json_section_path():
    table_id = uuid4()
    tables = SimpleNamespace(
        list_for_dataset=AsyncMock(
            return_value=[
                {
                    "id": table_id,
                    "name": "Actuals",
                    "current_snapshot_id": uuid4(),
                    "sheet_or_json_path": "Actuals#section[0:3]",
                }
            ]
        ),
        list_objects=AsyncMock(return_value=[]),
    )
    adapter = NativeDomains(
        SimpleNamespace(contains_type=lambda kind: kind is TableService, resolve=lambda kind: tables),
        admission=WorkAdmission(WorkAdmissionSettings()),
    )
    result = await adapter.schema(
        tenant_id="tenant", workspace_id=str(uuid4()), dataset_id=str(uuid4()), actor="issuer|owner"
    )
    assert result["tables"][0]["sheet_or_json_path"] == "Actuals#section[0:3]"

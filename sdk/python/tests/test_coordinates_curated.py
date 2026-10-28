# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import CoordinateCellPosition, CoordinateCellRequest, KnowledgeConfirmation, KoinonClient


async def test_coordinates_zero_based_cells_and_explicit_pending_consent_are_typed():
    calls = []
    manifest = {
        "dataset_id": "dataset",
        "table_id": "table",
        "native_dataset_id": "native",
        "native_table_id": "native-table",
        "snapshot_id": "used/old",
        "status": "partial",
        "parser_decisions": [{"name": "header", "value": False}],
        "dependencies": [{"name": "reader", "version": "1"}],
    }

    def handle(request):
        calls.append(request)
        if request.url.path.endswith("/confirm"):
            return httpx.Response(
                202,
                json={
                    "status": "pending",
                    "intent_id": "intent",
                    "operation_id": "intent",
                    "reason": "commit_outcome_unresolved",
                },
            )
        if request.url.path.endswith("/cells"):
            return httpx.Response(
                200,
                json={
                    "manifest": manifest,
                    "items": [
                        {
                            "output_row": 0,
                            "output_column": 0,
                            "source_row": 7,
                            "source_column": 0,
                            "source_path": ["Actuals", 0],
                            "header_cells": [{"row": 0, "column": 0}],
                            "source_type": "decimal",
                        }
                    ],
                },
            )
        return httpx.Response(200, json=manifest)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        observed = await client.table_coordinates("north", "data/set", "table", snapshot_id="used/old")
        selected = await client.table_coordinate_cells(
            "north",
            "data/set",
            "table",
            CoordinateCellRequest(snapshot_id="used/old", cells=(CoordinateCellPosition(row=0, column=0),)),
        )
        outcome = await client.confirm_knowledge(
            "north",
            "intent",
            KnowledgeConfirmation(confirm=True, expected_revision=1, authorization_digest="a" * 64),
            idempotency_key="explicit",
        )
    assert observed.parser_decisions[0].value is False
    assert selected.items[0].header_cells[0].row == 0
    assert selected.items[0].source_path == ("Actuals", 0)
    assert outcome.status == "pending" and len(calls) == 3
    assert calls[0].url.params["snapshot_id"] == "used/old"
    assert json.loads(calls[1].content)["cells"] == [{"row": 0, "column": 0}]
    assert calls[2].headers["idempotency-key"] == "explicit"


def test_non_boolean_confirmation_cannot_be_coerced_into_authorization():
    for value in (1, "true", False):
        with pytest.raises(ValidationError):
            KnowledgeConfirmation.model_validate(
                {"confirm": value, "expected_revision": 1, "authorization_digest": "a" * 64}
            )

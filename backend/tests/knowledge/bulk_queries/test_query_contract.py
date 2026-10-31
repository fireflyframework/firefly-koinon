# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError


def test_query_batch_is_bounded_independent_and_cannot_smuggle_conversation_or_sql():
    from koinon.knowledge.bulk_queries.dtos import QueryBatchCreate

    body = {
        "workspace_id": "workspace",
        "items": [{"client_item_id": "one", "dataset_id": "dataset", "question": "Count records"}],
    }
    assert QueryBatchCreate.model_validate(body).items[0].question == "Count records"
    for field, value in [
        ("conversation_id", "foreign"),
        ("sql", "SELECT 1"),
        ("question", " "),
        ("question", "q" * 8001),
    ]:
        bad = {"workspace_id": "workspace", "items": [{**body["items"][0], field: value}]}
        with pytest.raises(ValidationError):
            QueryBatchCreate.model_validate(bad)
    with pytest.raises(ValidationError):
        QueryBatchCreate.model_validate({"workspace_id": "workspace", "items": body["items"] * 2})
    with pytest.raises(ValidationError):
        QueryBatchCreate.model_validate(
            {
                "workspace_id": "workspace",
                "items": [{**body["items"][0], "client_item_id": str(i)} for i in range(21)],
            }
        )
    with pytest.raises(ValidationError):
        QueryBatchCreate.model_validate(
            {
                "workspace_id": "workspace",
                "items": [
                    {**body["items"][0], "client_item_id": str(i), "question": "😀" * 8000} for i in range(3)
                ],
            }
        )

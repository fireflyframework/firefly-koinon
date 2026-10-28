# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx

from koinon_sdk import AnswerAudit, KoinonClient


async def test_owner_audit_preserves_unknown_and_exact_used_revision():
    requests = []
    value = {
        "run_id": "run/one",
        "provenance_status": "recorded",
        "source_provenance_complete": True,
        "private_files": [
            {
                "id": "file",
                "filename": "Notes.md",
                "media_type": "text/markdown",
                "sha256": "a" * 64,
                "used_revision": 1,
                "availability": "expired",
            }
        ],
    }

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        audit = await client.run_audit("north", "run/one")
    assert isinstance(audit, AnswerAudit)
    assert audit.private_files[0].used_revision == 1
    assert audit.private_files[0].availability == "expired"
    assert requests[0].url.raw_path.endswith(b"/chat/runs/run%2Fone/audit")
    assert requests[0].headers["authorization"] == "Bearer fresh"
    old = AnswerAudit.model_validate({"run_id": "old", "provenance_status": "not_recorded"})
    assert old.source_provenance_complete is None
    assert old.generations == []


def test_engine_database_origin_and_snapshot_are_recorded_values_not_inferred_defaults():
    from koinon_sdk import NativeReadOrigin, NativeReadReceipt, SqlAttemptReceipt

    source = NativeReadOrigin.model_validate({"original_filename": "Ledger.xlsx", "schema": None})
    assert source.original_filename == "Ledger.xlsx" and source.schema_name is None
    attempt = SqlAttemptReceipt.model_validate(
        {
            "result_id": "result",
            "ordinal": 1,
            "stage": "execution",
            "statement_sha256": "b" * 64,
            "outcome": "succeeded",
            "executed": True,
            "snapshot_pins": {"Ledger": "snapshot"},
            "engine": "duckdb",
            "database": "memory",
            "catalog": "memory",
            "schema": "main",
            "execution_kind": "imported_snapshot",
            "dataset_id": "asset",
            "native_dataset_id": "native-asset",
            "tables": [{"table_id": "table", "table_name": "Ledger", "snapshot_id": "snapshot"}],
        }
    )
    assert attempt.database == "memory" and attempt.schema_name == "main"
    assert attempt.tables[0].snapshot_id == "snapshot"
    read = NativeReadReceipt.model_validate(
        {
            "result_id": "result",
            "stage": "retrieval",
            "domain": "documents",
            "tenant_id": "north",
            "workspace_id": "workspace",
            "entity_id": "document",
            "content_sha256": "c" * 64,
        }
    )
    assert read.engine is None and read.database is None and read.origin is None

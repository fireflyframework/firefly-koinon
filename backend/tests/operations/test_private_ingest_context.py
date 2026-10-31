# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from flycanon.core.mappers.job_mapper import to_ingest_job
from flyquery.core.services.ingest_jobs.ingest_job_service import _to_read
from pyfly.context.consumer_context import PRIVATE_CONSUMER_CONTEXT


def test_structured_public_job_and_nested_metadata_exclude_private_credential_envelope():
    identifier = uuid4()
    row = dict(
        id=identifier,
        tenant_id="north",
        workspace_id=identifier,
        dataset_id=identifier,
        job_kind="SAMPLE_REFRESH",
        status="PENDING",
        attempts=0,
        cost_cents=Decimal(0),
        request_json={
            "actor": "public-owner",
            PRIVATE_CONSUMER_CONTEXT: {"credential_id": "private-token-id"},
            "nested": [{"title": "visible", PRIVATE_CONSUMER_CONTEXT: {"subject": "private"}}],
        },
        result_json={PRIVATE_CONSUMER_CONTEXT: {"credential_id": "private-token-id"}},
        started_at=None,
        finished_at=None,
    )
    output = _to_read(row).model_dump(mode="json")
    assert output["request_json"] == {"actor": "public-owner", "nested": [{"title": "visible"}]}
    assert output["result_json"] == {}
    assert "private-token-id" not in str(output)


def test_canon_public_job_keeps_attribution_without_its_private_metadata_envelope():
    row = SimpleNamespace(
        id="job",
        status="queued",
        source_id=None,
        attempts=0,
        filename="one.txt",
        content_type="text/plain",
        uri=None,
        content_sha256=None,
        actor="public-owner",
        correlation_id="correlation",
        callback_url=None,
        error_code=None,
        error_message=None,
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
        updated_at=datetime.now(UTC),
        metadata_json={PRIVATE_CONSUMER_CONTEXT: {"credential_id": "private-token-id"}},
    )
    output = to_ingest_job(row).model_dump(mode="json")
    assert output["actor"] == "public-owner"
    assert "private-token-id" not in str(output) and PRIVATE_CONSUMER_CONTEXT not in str(output)

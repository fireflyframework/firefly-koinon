# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pydantic import ValidationError

from koinon.workers.execution import IngestionExecution


def facts(**changes):
    return dict(
        version=1,
        subject="issuer|owner",
        token_id="token-id",
        tenant_id="north",
        domain="canon",
        native_workspace_id="native",
        catalog_workspace_id="workspace",
        resource_ids=["source"],
        roles=["documents.embedding"],
        selections={
            "documents.embedding": {
                "assignment_id": "assignment",
                "revision": 1,
                "provider_id": "provider",
                "provider_revision": 1,
            }
        },
        **changes,
    )


def test_worker_context_has_no_caller_override_or_plaintext_credential_fields():
    captured = IngestionExecution.model_validate(facts())
    assert captured.token_id == "token-id" and captured.subject == "issuer|owner"
    with pytest.raises(ValidationError):
        IngestionExecution.model_validate({**facts(), "bearer_token": "secret"})
    with pytest.raises(ValidationError):
        IngestionExecution.model_validate({**facts(), "roles": ["*"]})


@pytest.mark.parametrize(
    "change", [{"subject": "owner"}, {"resource_ids": []}, {"domain": "other"}, {"version": True}]
)
def test_unprovable_or_unbounded_ingest_context_is_rejected(change):
    with pytest.raises(ValidationError):
        IngestionExecution.model_validate({**facts(), **change})

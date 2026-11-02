# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pending worker recovery remains bound to its authorized batch action receipt."""

import hashlib
import json
from typing import Literal

from pydantic import Field, ValidationError
from pyfly.kernel import ConflictException

from koinon.knowledge.bulk.dtos import BulkRecoveryAction, Digest, Input

PENDING_RECOVERY = "BULK_RECOVERY_REQUESTED"


class ProcessingRecoveryIntent(Input):
    operation: Literal["retry_processing", "finalize_publication"]
    starting_attempt: int = Field(strict=True, ge=1, le=2147483647)
    expected_revision: int = Field(strict=True, ge=1, le=2147483647)
    key_hash: Digest
    request_hash: Digest


def recovery_operation(job, item, batch) -> str | None:
    result = job.result
    if result is None or isinstance(result, dict) and "bulk_processing_recovery" not in result:
        if getattr(job, "error", None) != PENDING_RECOVERY:
            return None
        raise ConflictException("Admitted recovery metadata is missing", code="BULK_RECOVERY_STATE_CHANGED")
    try:
        if not isinstance(result, dict):
            raise ValueError("Invalid recovery metadata")
        intent = ProcessingRecoveryIntent.model_validate(result["bulk_processing_recovery"])
        body = BulkRecoveryAction(expected_revision=intent.expected_revision, operation=intent.operation)
        expected = hashlib.sha256(
            json.dumps(
                ["recover_processing:" + item.id, body.model_dump(), batch.token_id],
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        ).hexdigest()
        if (
            intent.request_hash != expected
            or batch.actions_json.get(intent.key_hash) != expected
            or not intent.starting_attempt <= job.attempts <= job.max_attempts
            or intent.expected_revision >= batch.revision
        ):
            raise ValueError("Unadmitted recovery metadata")
        return intent.operation
    except (KeyError, TypeError, ValueError, ValidationError):
        raise ConflictException(
            "Processing recovery does not match its admitted action", code="BULK_RECOVERY_STATE_CHANGED"
        ) from None

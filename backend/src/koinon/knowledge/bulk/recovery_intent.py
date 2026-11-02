# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pending worker recovery remains bound to its authorized batch action receipt."""

import hashlib
import json
from typing import Literal

from pydantic import AwareDatetime, Field, ValidationError, model_validator
from pyfly.kernel import ConflictException

from koinon.knowledge.bulk.dtos import BulkRecoveryAction, Digest, Identifier, Input

PENDING_RECOVERY = "BULK_RECOVERY_REQUESTED"


class NativeFailureProof(Input):
    version_id: Identifier
    event_id: Identifier
    failed_at: AwareDatetime
    attempt: int = Field(strict=True, ge=1, le=2147483647)
    attempt_started_at: AwareDatetime

    @model_validator(mode="after")
    def current_attempt(self):
        if self.failed_at < self.attempt_started_at:
            raise ValueError("Native failure predates the processing attempt")
        return self


class ProcessingRecoveryIntent(Input):
    operation: Literal["retry_processing", "finalize_publication"]
    starting_attempt: int = Field(strict=True, ge=1, le=2147483647)
    expected_revision: int = Field(strict=True, ge=1, le=2147483647)
    key_hash: Digest
    request_hash: Digest
    native_failure: NativeFailureProof | None = None

    @model_validator(mode="after")
    def matching_failure(self):
        if self.native_failure is not None and (
            self.operation != "retry_processing" or self.native_failure.attempt + 1 != self.starting_attempt
        ):
            raise ValueError("Native failure differs from the admitted retry")
        return self


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


def recovery_failure(job, item, batch) -> NativeFailureProof | None:
    if recovery_operation(job, item, batch) is None:
        return None
    return ProcessingRecoveryIntent.model_validate(job.result["bulk_processing_recovery"]).native_failure

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""In-process admission capability, never a transport or caller-controlled DTO."""

from dataclasses import dataclass

from koinon.catalog.errors import AccessDenied

_SEAL = object()


@dataclass(frozen=True)
class _Approval:
    seal: object
    intent_id: str
    revision: int
    digest: str
    credential_id: str
    key: str | None


def admitted_approval(row):
    return _Approval(
        _SEAL, row.id, row.revision, row.authorization_digest, row.credential_id, row.confirmation_key
    )


def require_approval(value, row, key, credential_id):
    if (
        not isinstance(value, _Approval)
        or value.seal is not _SEAL
        or (value.intent_id, value.revision, value.digest, value.credential_id, value.key)
        != (row.id, row.revision, row.authorization_digest, credential_id, key)
    ):
        raise AccessDenied(
            "Approve this external proposal in its application review", code="EXTERNAL_REVIEW_REQUIRED"
        )

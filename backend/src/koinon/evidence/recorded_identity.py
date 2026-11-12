# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opaque owner manifest revisions over bounded identities, never protected payloads."""

from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy.engine import Row

from koinon.assistants.entities import ChatThread
from koinon.assistants.source_reads import identities
from koinon.catalog.errors import AccessDenied
from koinon.evidence.reviews import digest
from koinon.security.authority import primary_authority


def identity_value(value):
    if isinstance(value, bytes | memoryview):
        return {"sha256": bytes(value).hex()}
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise AccessDenied("This evidence is unavailable", code="EVIDENCE_UNAVAILABLE")
        return {"timestamp": value.astimezone(UTC).isoformat()}
    if isinstance(value, tuple | list | Row):
        return [identity_value(item) for item in value]
    if isinstance(value, dict):
        return {key: identity_value(item) for key, item in value.items()}
    if value is None or isinstance(value, str | int | bool):
        return value
    raise AccessDenied("This evidence is unavailable", code="EVIDENCE_UNAVAILABLE")


def manifest_identity_revision(actor, tenant, thread, messages, identity):
    return digest(
        {
            "domain": "koinon.owner-evidence-manifest.identity.v1",
            "actor": actor,
            "tenant": tenant,
            "thread": thread,
            "messages": sorted(messages),
            "identity": identity_value(identity),
        }
    )


@repository(name="evidence.history_identity")
class EvidenceHistoryIdentity(Repository[ChatThread, str]):
    async def revision(self, actor, tenant, thread, messages):
        if not 1 <= len(messages) <= 200 or len(set(messages)) != len(messages):
            raise AccessDenied("This evidence is unavailable", code="EVIDENCE_UNAVAILABLE")
        async with primary_authority(fresh=True):
            session = self._require_session()
            if session.get_bind().dialect.name != "postgresql":
                # Identity fingerprints are deliberately not fabricated by compatibility databases.
                raise AccessDenied("This evidence is unavailable", code="EVIDENCE_UNAVAILABLE")
            captured = await identities(session, actor, tenant, thread, {"message_ids": tuple(messages)})
            if not set(messages).issubset(row[0] for row in captured[2]):
                raise AccessDenied("This evidence is unavailable", code="EVIDENCE_UNAVAILABLE")
        return manifest_identity_revision(actor, tenant, thread, messages, captured)

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import service
from pyfly.kernel import ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import EvidenceManifest
from koinon.evidence.reviews import EvidenceReviews, digest
from koinon.exports.dtos import MessageSelection


@service(name="evidence.manifests")
class ConversationEvidence:
    def __init__(self, reviews: EvidenceReviews):
        self.reviews = reviews

    async def conversation(self, subject, tenant_id, body: MessageSelection) -> EvidenceManifest:
        port = self.reviews.snapshots.get()
        if port is None:
            raise ServiceUnavailableException(
                "Conversation sources are not configured", code="CONVERSATION_SNAPSHOT_UNAVAILABLE"
            )
        snapshot = await port.snapshot(subject, tenant_id, body.thread_id, body.message_ids)
        if (
            snapshot.owner_subject != subject
            or snapshot.tenant_id != tenant_id
            or snapshot.thread_id != body.thread_id
            or set(body.message_ids) != {item.id for item in snapshot.messages}
        ):
            raise AccessDenied("This evidence is unavailable", code="EVIDENCE_UNAVAILABLE")
        await self.reviews.access.check(
            subject,
            tenant_id,
            snapshot.sources,
            permission="evidence:read",
            originating_token_ids=snapshot.originating_token_ids,
        )
        resolver = self.reviews.sources.get()
        sources = (
            await resolver.resolve(subject, tenant_id, snapshot.sources) if resolver else snapshot.sources
        )
        omissions = []
        if not snapshot.source_manifest_complete:
            omissions.append("Historical source provenance is incomplete.")
        if any(message.private_derived for message in snapshot.messages):
            omissions.append("Private attachment files and their metadata are excluded.")
        return EvidenceManifest(
            revision=digest(
                {"snapshot": snapshot.revision, "sources": [item.model_dump(mode="json") for item in sources]}
            ),
            sources=sources,
            complete=snapshot.source_manifest_complete,
            omissions=tuple(omissions),
        )

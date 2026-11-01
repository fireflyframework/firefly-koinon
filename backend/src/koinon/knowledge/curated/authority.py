# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from datetime import UTC, datetime

from pyfly.container import Provider, service
from pyfly.kernel import (
    ConflictException,
    InvalidRequestException,
    PayloadTooLargeException,
    ServiceUnavailableException,
)
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.assistants.memory.egress import MemoryEgress
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import PARENTS, CatalogService
from koinon.evidence.dtos import ConversationSnapshot
from koinon.evidence.ports import (
    ConversationOutputPort,
    ConversationSnapshotPort,
    SourceResolverPort,
    TransitiveSourceResolverPort,
    WriteSourceResolverPort,
)
from koinon.knowledge.curated.dtos import (
    ConversationOrigin,
    DocumentEvidence,
    ExternalProposalEvidence,
    ExternalProposalOrigin,
    KnowledgeDestination,
    KnowledgeEvidence,
    StructuredEvidence,
    UserStatementEvidence,
)
from koinon.knowledge.external_reviews.read_receipt_ports import ExternalReadReceiptPort


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


@service(name="knowledge.curated.authority")
class CuratedAuthority:
    def __init__(
        self,
        catalog: CatalogService,
        snapshots: Provider[ConversationSnapshotPort | None],
        sources: Provider[SourceResolverPort | None],
        read_receipts: Provider[ExternalReadReceiptPort | None] | None = None,
        memory: Provider[MemoryEgress | None] | None = None,
        outputs: Provider[ConversationOutputPort | None] | None = None,
    ):
        self.catalog, self.snapshots, self.sources = catalog, snapshots, sources
        self.read_receipts = read_receipts
        self.memory = memory
        self.outputs = outputs

    async def output_check(self, subject, tenant_id, request):
        origin = request.get("origin", {})
        if origin.get("kind") != "conversation":
            return
        selected = ConversationOrigin.model_validate(origin)
        captured = request.get("_output_context")
        if not isinstance(captured, dict):
            raise ConflictException(
                "Review a fresh preview of the selected answer", code="KNOWLEDGE_OUTPUT_REVIEW_REQUIRED"
            )
        try:
            snapshot = ConversationSnapshot.model_validate(captured)
        except ValueError as error:
            raise ConflictException(
                "Review a fresh preview of the selected answer", code="KNOWLEDGE_OUTPUT_REVIEW_REQUIRED"
            ) from error
        port = self.outputs.get() if self.outputs else None
        if port is None:
            raise ServiceUnavailableException(
                "Regenerate the selected answer before publishing it",
                code="CONVERSATION_OUTPUT_UNAVAILABLE",
            )
        await port.authorize_output(
            subject, tenant_id, selected.thread_id, list(selected.message_ids), snapshot=snapshot
        )

    async def destination(self, subject, tenant_id, identifier, *, write=True):
        chain, seen, current = [], set(), identifier
        while current is not None:
            if current in seen or len(seen) >= 16:
                raise AccessDenied(
                    "Select a valid knowledge destination", code="INVALID_KNOWLEDGE_DESTINATION"
                )
            seen.add(current)
            row = await self.catalog.get(subject, tenant_id, current)
            if row.status == "archived":
                raise AccessDenied("Knowledge destination is archived", code="RESOURCE_ARCHIVED")
            chain.append(row)
            current = row.parent_id
        if [row.kind for row in chain] not in (
            ["collection", "project", "workspace"],
            ["corpus", "project", "workspace"],
        ):
            raise AccessDenied("Choose a collection or corpus", code="INVALID_KNOWLEDGE_DESTINATION")
        workspace, project = chain[-1], chain[-2]
        for index, row in enumerate(chain):
            parent = chain[index + 1] if index + 1 < len(chain) else None
            if (
                row.workspace_id != workspace.id
                or (parent.kind if parent else None) not in PARENTS[row.kind]
                or (row.kind != "workspace" and row.project_id != project.id)
            ):
                raise AccessDenied(
                    "Knowledge destination ancestry is invalid", code="INVALID_KNOWLEDGE_DESTINATION"
                )
        if write:
            for permission in ("catalog:write", "ingest:write"):
                await self.catalog.authorize(subject, tenant_id, permission, workspace.id)
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, chain[0], write=write)
        return KnowledgeDestination(
            id=identifier,
            workspace_id=workspace.id,
            project_id=project.id,
            name=chain[0].name,
            ancestry_digest=digest(
                [(row.id, row.kind, row.parent_id, row.status, row.updated_at.isoformat()) for row in chain]
            ),
        )

    async def observe(
        self, subject, tenant_id, request, recorded_at, *, memory_capture=None, output_capture=None
    ):
        context = SecurityContextHolder.get_context()
        token = context.attributes.get("koinon_token_id") if context else None
        origins = {token} if token else set()
        if isinstance(request.origin, ExternalProposalOrigin):
            restriction = self.catalog.restriction
            grant = await restriction.grant(subject) if restriction else None
            if grant is None or grant.tenant_id != tenant_id:
                raise AccessDenied("An active external credential is required", code="TOKEN_UNAVAILABLE")
            evidence: tuple[KnowledgeEvidence, ...] = (
                ExternalProposalEvidence(
                    text=request.content.body,
                    sha256=hashlib.sha256(request.content.body.encode()).hexdigest(),
                    submitted_by=subject,
                    credential_id=grant.id,
                    application_id=grant.authorized_application_id,
                    source_receipt_ids=request.origin.source_receipt_ids,
                    recorded_at=recorded_at,
                ),
            )
            if request.origin.source_receipt_ids:
                receipts = self.read_receipts.get() if self.read_receipts else None
                if receipts is None:
                    raise ServiceUnavailableException(
                        "Source read receipts are unavailable", code="KNOWLEDGE_PROVENANCE_UNAVAILABLE"
                    )
                references, read_origins = await receipts.resolve(
                    subject, tenant_id, request.origin.source_receipt_ids
                )
                if not references:
                    raise ServiceUnavailableException(
                        "The selected receipts contain no captured sources",
                        code="KNOWLEDGE_PROVENANCE_UNAVAILABLE",
                    )
                if len(references) > 499:
                    raise InvalidRequestException(
                        "Select fewer source read receipts", code="KNOWLEDGE_PROVENANCE_LIMIT"
                    )
                if any(reference.kind not in {"document", "dataset"} for reference in references):
                    raise ServiceUnavailableException(
                        "Transitive source provenance is not qualified", code="CURATED_DERIVATION_UNQUALIFIED"
                    )
                evidence = (
                    *evidence,
                    *(
                        DocumentEvidence(source=reference)
                        if reference.kind == "document"
                        else StructuredEvidence(source=reference)
                        for reference in references
                    ),
                )
                origins.update(read_origins)
                await self.evidence(subject, tenant_id, evidence)
            return evidence, tuple(sorted(origins | {grant.id}))
        if not isinstance(request.origin, ConversationOrigin):
            return (
                UserStatementEvidence(
                    text=request.content.body,
                    sha256=hashlib.sha256(request.content.body.encode()).hexdigest(),
                    author_subject=subject,
                    recorded_at=recorded_at,
                ),
            ), tuple(sorted(origins))
        snapshots = self.snapshots.get()
        if snapshots is None:
            raise ServiceUnavailableException(
                "Conversation provenance is unavailable", code="KNOWLEDGE_PROVENANCE_UNAVAILABLE"
            )
        snapshot = await snapshots.snapshot(
            subject, tenant_id, request.origin.thread_id, list(request.origin.message_ids)
        )
        bindings = getattr(snapshot, "memory_bindings", ())
        memory = self.memory.get() if self.memory else None
        remembered = await memory.authorize(subject, tenant_id, bindings) if memory else False
        if bindings and memory is None:
            raise ServiceUnavailableException(
                "Conversation authority is unavailable", code="MEMORY_UNAVAILABLE"
            )
        if memory_capture is not None:
            memory_capture.update(
                {"present": remembered, "bindings": [value.model_dump(mode="json") for value in bindings]}
            )
        if (
            snapshot.owner_subject != subject
            or snapshot.tenant_id != tenant_id
            or not snapshot.source_manifest_complete
            or any(message.private_derived for message in snapshot.messages)
            or not snapshot.sources
        ):
            raise AccessDenied(
                "Select complete shared evidence or explicitly author your own statement",
                code="KNOWLEDGE_PROVENANCE_REQUIRED",
            )
        if output_capture is not None:
            captured = snapshot.model_dump(mode="json", include=set(ConversationSnapshot.model_fields))
            if len(json.dumps(captured, ensure_ascii=False).encode()) > 5 * 1024 * 1024:
                raise PayloadTooLargeException(
                    "Select fewer messages for this preview", code="SNAPSHOT_TOO_LARGE"
                )
            output_capture.update(captured)
        direct_sources = snapshot.sources
        if any(source.kind == "knowledge_version" for source in direct_sources):
            resolver = self.sources.get()
            if not isinstance(resolver, TransitiveSourceResolverPort):
                raise ServiceUnavailableException(
                    "Transitive source provenance is unavailable", code="CURATED_DERIVATION_UNQUALIFIED"
                )
            direct_sources = await resolver.resolve_bounds(subject, tenant_id, direct_sources)
        evidence = tuple(
            DocumentEvidence(source=source)
            if source.kind == "document"
            else StructuredEvidence(source=source)
            for source in direct_sources
        )
        if remembered and memory is not None:
            inherited = await memory.remembered_sources(subject, tenant_id, bindings)
            if any(source.kind == "knowledge_version" for source in inherited):
                resolver = self.sources.get()
                if not isinstance(resolver, TransitiveSourceResolverPort):
                    raise ServiceUnavailableException(
                        "Transitive source provenance is unavailable", code="CURATED_DERIVATION_UNQUALIFIED"
                    )
                inherited = await resolver.resolve_bounds(subject, tenant_id, inherited)
            evidence = (
                *evidence,
                *(
                    DocumentEvidence(source=source, basis="remembered_context")
                    if source.kind == "document"
                    else StructuredEvidence(source=source, basis="remembered_context")
                    for source in inherited
                ),
            )
        origins.update(snapshot.originating_token_ids)
        await self.evidence(subject, tenant_id, evidence)
        return evidence, tuple(sorted(origins))

    async def memory_check(
        self,
        subject,
        tenant_id,
        values,
        *,
        transfer=False,
        consent=False,
        release_check=None,
        token_ids=(),
        asset_ids=(),
        release=None,
    ):
        from koinon.assistants.memory.egress_dtos import MemoryEgressBinding

        bindings = tuple(MemoryEgressBinding.model_validate(value) for value in values.get("bindings", []))
        port = self.memory.get() if self.memory else None
        if bindings and port is None:
            raise ServiceUnavailableException(
                "Conversation authority is unavailable", code="MEMORY_UNAVAILABLE"
            )
        if port:
            await port.authorize(
                subject,
                tenant_id,
                bindings,
                transfer=transfer,
                consent=consent,
                release_check=release_check,
                token_ids=token_ids,
                asset_ids=asset_ids,
                release=release,
            )

    async def evidence(self, subject, tenant_id, evidence, *, exact=True):
        sources = tuple(
            value.source for value in evidence if isinstance(value, DocumentEvidence | StructuredEvidence)
        )
        if not sources:
            return
        for source in sources:
            entry = await self.catalog.get(subject, tenant_id, source.asset_id)
            if exact:
                permission = "knowledge:search" if source.kind == "document" else "query:execute"
                await self.catalog.authorize(subject, tenant_id, permission, entry.workspace_id)
        resolver = self.sources.get()
        if resolver is None:
            raise ServiceUnavailableException(
                "Exact source validation is unavailable", code="KNOWLEDGE_PROVENANCE_UNAVAILABLE"
            )
        resolve = resolver.resolve
        if exact and any(source.source_part_id for source in sources):
            if not isinstance(resolver, WriteSourceResolverPort):
                raise ServiceUnavailableException(
                    "Current source revision locking is unavailable", code="KNOWLEDGE_PROVENANCE_UNAVAILABLE"
                )
            resolve = resolver.resolve_for_write
        resolved = await resolve(subject, tenant_id, sources)
        if len(resolved) != len(sources) or any(
            current.id != used.id
            or current.used_revision != used.used_revision
            or exact
            and (current.availability != "available" or current.current_revision != used.used_revision)
            for used, current in zip(sources, resolved, strict=True)
        ):
            raise ConflictException(
                "A source changed or is unavailable; review a new preview", code="KNOWLEDGE_SOURCE_CHANGED"
            )

    async def origins(self, subject, tenant_id, destination_id, evidence, token_ids, *, write_token_ids=()):
        if not token_ids:
            return
        restriction = self.catalog.restriction
        if restriction is None:
            raise ServiceUnavailableException(
                "Originating authority validation is unavailable", code="TOKEN_AUTHORITY_UNAVAILABLE"
            )
        for identifier in token_ids:
            token = await restriction.tokens.find_by_id(identifier)
            if (
                token is None
                or token.subject != subject
                or token.tenant_id != tenant_id
                or token.revoked_at is not None
                or token.expires_at <= datetime.now(UTC)
            ):
                raise AccessDenied("The originating authority is no longer valid", code="TOKEN_UNAVAILABLE")
            issuer, _, sub = subject.partition("|")
            with SecurityContextHolder.using(
                SecurityContext(
                    user_id=sub, attributes={"iss": issuer, "sub": sub, "koinon_token_id": identifier}
                )
            ):
                if identifier in write_token_ids:
                    await self.destination(subject, tenant_id, destination_id)
                await self.evidence(subject, tenant_id, evidence)

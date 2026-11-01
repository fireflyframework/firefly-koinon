# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from test_curated_intents import curated as curated
from test_curated_intents import input_for

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.document_part_receipts import verify_part_sources
from koinon.knowledge.evidence_capture import document_reference
from koinon.knowledge.evidence_sources import NativeSourceResolver


async def test_knowledge_confirmation_rejects_a_changed_ingestion_head_while_history_remains_readable(
    curated,
):
    from pyfly.kernel import ConflictException

    from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot, SourceReference

    service, catalog, destination, _ = curated
    source = await catalog.create(
        "issuer|owner", "north", kind="source", name="Source", parent_id=destination.id
    )
    document = await catalog.create(
        "issuer|owner", "north", kind="document", name="Document", parent_id=source.id
    )
    text = "Threshold47"
    digest = sha256(text.encode()).hexdigest()
    reference = SourceReference(
        id="part-reference",
        asset_id=document.id,
        source_id=source.id,
        title="Document",
        kind="document",
        used_revision="source-part-sha256:" + digest,
        source_version_id="raw-version",
        extraction_id="whole-view",
        source_part_id="part",
        source_part_sha256=digest,
        page_basis="recorded_loader",
        quote=text,
    )
    snapshot = ConversationSnapshot(
        thread_id="thread",
        tenant_id="north",
        owner_subject="issuer|owner",
        title="Research",
        revision="a" * 64,
        messages=(
            ConversationMessage(
                id="answer", role="assistant", text=text, status="completed", revision="b" * 64
            ),
        ),
        sources=(reference,),
        source_manifest_complete=True,
    )
    head = {"source_version_id": "raw-version", "extraction_id": "ingestion"}

    class Domains:
        async def document_parts(self, **arguments):
            return (
                SimpleNamespace(
                    part_id="part",
                    source_id="native-source",
                    source_version_id="raw-version",
                    extraction_id="whole-view",
                    ingestion_extraction_id="ingestion",
                    sha256=digest,
                    text=text,
                    page=None,
                ),
            )

        async def document_revision(self, **arguments):
            return head

    validated_outputs = []

    class Snapshots:
        async def snapshot(self, *args):
            return snapshot

        async def authorize_output(self, subject, tenant_id, thread_id, message_ids, *, snapshot=None):
            assert (subject, tenant_id, thread_id, message_ids) == (
                "issuer|owner", "north", "thread", ["answer"]
            )
            assert snapshot.messages[0].text == text
            assert snapshot.sources == (reference,)
            validated_outputs.append(snapshot.messages[0].id)

    class Sources:
        async def resolve(self, subject, tenant_id, sources):
            binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-space")
            result = await verify_part_sources(
                Domains(), subject, tenant_id, [(value, binding) for value in sources], current=True
            )
            return tuple(result[value.id] for value in sources)

        resolve_for_write = resolve

    selected = Snapshots()
    service.authority.snapshots = SimpleNamespace(get=lambda: selected)
    service.authority.outputs = SimpleNamespace(get=lambda: selected)
    service.authority.sources = SimpleNamespace(get=lambda: Sources())
    preview = await service.preview(
        "issuer|owner",
        "north",
        input_for(
            destination,
            action="create_published",
            origin={"kind": "conversation", "thread_id": "thread", "message_ids": ["answer"]},
        ),
    )
    head["extraction_id"] = "replacement-ingestion"
    service.native = SimpleNamespace(
        get=lambda: pytest.fail("Stale source must fail before native commit resolution")
    )
    with pytest.raises(ConflictException) as failure:
        await service.confirm(
            "issuer|owner",
            "north",
            preview.id,
            {
                "confirm": True,
                "expected_revision": preview.revision,
                "authorization_digest": preview.authorization_digest,
            },
            "explicit",
        )
    assert failure.value.code == "KNOWLEDGE_SOURCE_CHANGED"
    assert validated_outputs == ["answer"]
    await service.authority.evidence("issuer|owner", "north", preview.evidence, exact=False)


async def test_exact_part_hash_scope_and_quote_are_verified_without_chunks_or_current_pointer():
    text = "Recorded section contains the renewal threshold47."
    digest = sha256(text.encode()).hexdigest()
    capture = NativeEvidenceReceipt("issuer|reader", "north")
    capture.search(
        "north",
        "native-space",
        "issuer|reader",
        [
            {
                "chunk_id": "part",
                "source_id": "native-source",
                "content": "renewal threshold47",
                "page": None,
                "metadata": {
                    "source_version_id": "version",
                    "extraction_id": "view",
                    "source_part_id": "part",
                    "source_part_sha256": digest,
                    "page_basis": "recorded_loader",
                    "recorded_page": "7",
                },
            }
        ],
    )
    reference = document_reference(
        capture.documents["part"], asset_id="canonical-document", source_id="canonical-source", title="Report"
    )
    assert reference.chunk_id is None and reference.page is None and reference.recorded_page == 7
    assert reference.used_revision == "source-part-sha256:" + digest
    calls = []
    head = {"source_version_id": "version", "extraction_id": "ingestion-parent"}

    class Domains:
        async def document_parts(self, **arguments):
            calls.append(arguments)
            return (
                SimpleNamespace(
                    part_id="part",
                    source_id="native-source",
                    source_version_id="version",
                    extraction_id="view",
                    ingestion_extraction_id="ingestion-parent",
                    sha256=digest,
                    text=text,
                    page=7,
                ),
            )

        async def document_revision(self, **arguments):
            return head

        def _resolve(self, *args):
            pytest.fail("Immutable parts must never resolve through current source/chunk repositories")

    binding = SimpleNamespace(native_id="native-source", native_workspace_id="native-space")
    resolver = NativeSourceResolver(None, Domains(), None)
    found = await resolver.document("issuer|reader", "north", reference, binding)
    assert found == {"availability": "available", "current_revision": reference.used_revision}
    assert calls[0]["source_version_id"] == "version" and calls[0]["part_ids"] == ("part",)
    with pytest.raises(AccessDenied):
        await resolver.document(
            "issuer|reader", "north", reference.model_copy(update={"quote": "not present"}), binding
        )
    calls.clear()
    result = await verify_part_sources(
        Domains(),
        "issuer|reader",
        "north",
        [
            (reference, binding),
            (reference.model_copy(update={"id": "second", "quote": "Recorded section"}), binding),
        ],
    )
    assert len(calls) == 1 and len(result) == 2
    head["extraction_id"] = "different-ingestion"
    stale = await resolver.document("issuer|reader", "north", reference, binding)
    assert stale == {"availability": "changed", "current_revision": None}
    assert (await verify_part_sources(Domains(), "issuer|reader", "north", [(reference, binding)]))[
        reference.id
    ].availability == "available"
    with pytest.raises(ValidationError):
        type(reference).model_validate({**reference.model_dump(), "source_version_id": None})

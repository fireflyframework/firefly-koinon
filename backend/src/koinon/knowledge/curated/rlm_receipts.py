# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Admit whole acknowledged curated inputs before native RLM code sees their bytes."""

from __future__ import annotations

from hashlib import sha256
from threading import get_ident
from typing import TYPE_CHECKING

from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.knowledge_integrity import validate_meta, verify_view
from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta, WholeKnowledgeRead

from koinon.knowledge.curated.corpus_dtos import ServingVersion
from koinon.knowledge.curated.rlm_mappers import database_context, fingerprint, part_source
from koinon.knowledge.rlm_provenance import EXECUTION_READ, unavailable

if TYPE_CHECKING:
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

MODELS = frozenset({"rlm.root", "rlm.submodel", "rlm.forced_final", "rlm.selector"})
VIEW = "rlm.knowledge_view.v1"


def admit(receipt: NativeEvidenceReceipt, tenant_id, workspace_id, actor, admitted, selections) -> None:
    receipt.scope(tenant_id, workspace_id, actor)
    pending = {}
    if len(selections) > 128 or len(selections) > len(admitted):
        raise unavailable()
    for selected in selections:
        if type(selected) is not ServingVersion:
            raise unavailable()
        bound = admitted.get(selected.native_item_id)
        if (
            bound is None
            or selected.native_workspace_id != workspace_id
            or (selected.item_id, selected.workspace_id) != (bound[0].id, bound[0].workspace_id)
        ):
            raise unavailable()
        key = (workspace_id, selected.item_id)
        if key in pending or (
            key in receipt.curated_rlm.admissions and receipt.curated_rlm.admissions[key] != selected
        ):
            raise unavailable()
        pending[key] = selected
    receipt.curated_rlm.admissions.update(pending)


def require_scope(
    receipt: NativeEvidenceReceipt, scope: provenance.Observation | None, *, worker: bool
) -> provenance.Observation:
    if (
        scope is None
        or provenance.current() is not scope
        or not scope.active
        or receipt.closed
        or scope.observer is not receipt
        or scope.task is not receipt.owner
        or scope.task.done()
        or scope.task.cancelling()
        or scope.loop.is_closed()
        or scope.tenant_id != receipt.tenant_id
        or scope.actor != receipt.subject
        or worker
        and get_ident() not in scope.threads
    ):
        raise unavailable()
    return scope


def corpus_meta(
    receipt: NativeEvidenceReceipt, meta: KnowledgeVersionMeta, scope: provenance.Observation
) -> None:
    require_scope(receipt, scope, worker=False)
    if type(meta) is not KnowledgeVersionMeta:
        raise unavailable()
    validate_meta(meta)
    selection = receipt.curated_rlm.admissions.get((scope.workspace_id, meta.item_id))
    if (
        selection is None
        or (meta.tenant_id, meta.workspace_id) != (scope.tenant_id, scope.workspace_id)
        or (
            meta.item_id,
            meta.canonical_workspace_id,
            meta.native_item_id,
            meta.workspace_id,
            meta.version_id,
            meta.version,
        )
        != (
            selection.item_id,
            selection.workspace_id,
            selection.native_item_id,
            selection.native_workspace_id,
            selection.version_id,
            selection.version,
        )
    ):
        raise unavailable()
    key = (scope.workspace_id, meta.item_id)
    previous = receipt.curated_rlm.metadata.get(key)
    if previous is not None and previous != meta:
        raise unavailable()
    receipt.curated_rlm.metadata[key] = meta


def sync(
    receipt: NativeEvidenceReceipt,
    stage: str,
    content: str,
    identifiers: tuple[str, ...],
    scope: provenance.Observation,
) -> None:
    require_scope(receipt, scope, worker=stage != "rlm.corpus")
    if stage not in {"rlm.corpus", *MODELS} or not identifiers or len(identifiers) > 128:
        raise unavailable()
    pending = []
    for identifier in identifiers:
        key = (scope.workspace_id, identifier)
        meta = receipt.curated_rlm.metadata.get(key)
        if meta is None or identifier not in scope.knowledge_ids:
            raise unavailable()
        pending.append(
            fingerprint(meta, stage, sha256(content.encode()).hexdigest(), receipt.curated_rlm.views.get(key))
        )
    receipt.budget.check(receipt, reads=pending)
    receipt.native_reads.extend(pending)


def view_parts(
    receipt: NativeEvidenceReceipt,
    meta: KnowledgeVersionMeta,
    view: WholeKnowledgeRead,
    scope: provenance.Observation,
) -> None:
    require_scope(receipt, scope, worker=True)
    key = (scope.workspace_id, meta.item_id)
    if (
        receipt.curated_rlm.metadata.get(key) != meta
        or meta.item_id not in scope.knowledge_ids
        or type(view) is not WholeKnowledgeRead
        or view.meta != meta
    ):
        raise unavailable()
    provenance.authority(scope)
    verify_view(view)
    previous = receipt.curated_rlm.views.get(key)
    if previous is not None:
        if previous != view:
            raise unavailable()
        return
    pending_by_id = {part.part_id: part_source(meta, part.part_id, part.text) for part in view.parts}
    pending = list(pending_by_id.values())
    proofs = {
        part.part_id: (
            meta.canonical_workspace_id,
            meta.workspace_id,
            meta.native_item_id,
            sha256(part.text.encode()).hexdigest(),
            pending_by_id[part.part_id],
            database_context(view),
        )
        for part in view.parts
    }
    if any(
        identifier in receipt.knowledge_proofs and receipt.knowledge_proofs[identifier] != proof
        for identifier, proof in proofs.items()
    ):
        raise unavailable()
    reads = [
        fingerprint(meta, VIEW, view.manifest_sha256, view),
        fingerprint(meta, "rlm.read", meta.body_sha256, view),
    ]
    receipt.budget.check(receipt, knowledge_sources=pending, reads=reads)
    receipt.knowledge_sources.update(pending_by_id)
    receipt.knowledge_proofs.update(proofs)
    receipt.curated_rlm.views[key] = view
    receipt.native_reads.extend(reads)


def execution_read(
    receipt: NativeEvidenceReceipt,
    meta: KnowledgeVersionMeta,
    view: WholeKnowledgeRead,
    scope: provenance.Observation,
) -> None:
    require_scope(receipt, scope, worker=True)
    key = (scope.workspace_id, meta.item_id)
    if (
        receipt.curated_rlm.metadata.get(key) != meta
        or receipt.curated_rlm.views.get(key) != view
        or meta.item_id not in scope.knowledge_ids
    ):
        raise unavailable()
    provenance.authority(scope)
    read = fingerprint(meta, EXECUTION_READ, meta.body_sha256, view)
    receipt.budget.check(receipt, reads=[read])
    receipt.native_reads.append(read)
    receipt.curated_rlm.execution[key] = view


def execution_views(receipt: NativeEvidenceReceipt) -> frozenset[tuple[str, str]]:
    observed = set()
    for key, view in receipt.curated_rlm.execution.items():
        if (
            receipt.curated_rlm.views.get(key) == view
            and fingerprint(view.meta, EXECUTION_READ, view.meta.body_sha256, view) in receipt.native_reads
        ):
            observed.add(key)
    return frozenset(observed)

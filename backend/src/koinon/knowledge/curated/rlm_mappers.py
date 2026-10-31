# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure knowledge-version source and fingerprint mappings."""

import json
from hashlib import sha256

from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta, WholeKnowledgeRead

from koinon.evidence.dtos import SourceReference
from koinon.knowledge.capture_dtos import NativeDatabaseContext, NativeReadFingerprint


def part_source(meta: KnowledgeVersionMeta, part_id: str, quote: str) -> SourceReference:
    values = dict(
        asset_id=meta.item_id,
        knowledge_item_id=meta.item_id,
        knowledge_version_id=meta.version_id,
        knowledge_version=meta.version,
        title=meta.title,
        kind="knowledge_version",
        used_revision="knowledge-content-sha256:" + meta.content_sha256,
        chunk_id=part_id,
        quote=quote,
    )
    identifier = sha256(
        json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return SourceReference.model_validate({"id": identifier, **values})


def database_context(view: WholeKnowledgeRead | None) -> NativeDatabaseContext:
    return (
        NativeDatabaseContext(
            view.database.engine, view.database.database, view.database.catalog, view.database.schema
        )
        if view is not None
        else NativeDatabaseContext()
    )


def fingerprint(
    meta: KnowledgeVersionMeta, stage: str, digest: str, view: WholeKnowledgeRead | None = None
) -> NativeReadFingerprint:
    database = database_context(view)
    return NativeReadFingerprint(
        stage,
        "knowledge",
        meta.tenant_id,
        meta.canonical_workspace_id,
        meta.item_id,
        digest,
        (meta.item_id,),
        (),
        engine=database.engine,
        database=database.database,
        catalog=database.catalog,
        schema=database.schema,
        read_kind="knowledge_version",
        knowledge_item_id=meta.item_id,
        knowledge_version_id=meta.version_id,
        knowledge_version=meta.version,
    )

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Inactive mapping review with canonical destination policy and fresh folder proofs."""

import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import service

from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.dtos import SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import SourceConnectionService, _no_remote_unit
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry, overlaps
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput, MappingReviewOutput
from koinon.integrations.content_sources.mapping_entities import SourceMapping
from koinon.integrations.content_sources.mapping_repository import SourceMappingRepository
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.knowledge.bulk.authority import BulkAuthority
from koinon.security.authority import primary_authority


@service(name="content_sources.mapping_reviews")
class SourceMappingReviews:
    def __init__(
        self,
        authority: BulkAuthority,
        connections: SourceConnectionService,
        browser: PersonalSourceBrowser,
        records: SourceMappingRepository,
    ):
        self.authority, self.connections = authority, connections
        self.browser, self.records = browser, records
        self._slots = asyncio.Semaphore(4)

    async def review(self, actor: str, tenant: str, request: MappingReviewInput) -> MappingReviewOutput:
        _no_remote_unit()
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self.authority.destination(actor, tenant, request.destination, write=True)
        connection = await self.connections.connected(actor, tenant, request.connection_id)
        account = connection.account
        if account is None:
            raise SourceError("reconnect_required")
        async with primary_authority(read_only=False):
            await self.authority.destination(actor, tenant, request.destination, write=True)
            admitted_at = datetime.now(UTC)
            candidates = await self.records.review_candidates(
                tenant, account, request.drive_id, at=admitted_at
            )

        # A single current grant spans both observations; refresh/reconnect invalidates the proof.
        grant = await self.connections.read_grant(actor, tenant, request.connection_id, account)
        scope = SourceScope(account, request.drive_id)
        roots = tuple(dict.fromkeys((request.root_id, *(row.root_id for row in candidates))))
        try:
            async with (
                asyncio.timeout(120),
                self._slots,
                self.browser._source(scope, _OperationToken(account, grant.token)) as adapter,
            ):
                proof = await FolderAncestry(adapter, scope).capture(roots)
                if any(
                    overlaps(proof, request.root_id, request.recursive, row.root_id, row.recursive)
                    for row in candidates
                ):
                    raise SourceError("scope_mismatch")
                confirmed = await FolderAncestry(adapter, scope).capture(roots)
                if confirmed != proof:
                    raise SourceError("version_changed")
        except TimeoutError:
            raise SourceError("timeout") from None
        await self.connections.confirm_read_grant(actor, tenant, request.connection_id, grant)
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self.authority.destination(actor, tenant, request.destination, write=True)
            row = await self.connections.connections.owned(tenant, actor, request.connection_id, lock=True)
            if (
                row is None
                or row.status != "connected"
                or row.secret_ciphertext is None
                or row.refresh_operation is not None
                or row.revision != grant.revision
                or row.provider != account.provider
                or row.external_subject != account.subject
                or row.external_tenant != account.tenant_id
                or row.issuer is None
                or row.config_fingerprint != grant.config_fingerprint
                or tuple(row.scopes) != grant.scopes
                or self.connections.registrations.get(account.provider).fingerprint
                != grant.config_fingerprint
            ):
                raise SourceError("authority_changed")
            current = await self.records.review_candidates(tenant, account, request.drive_id, at=admitted_at)
            if current != candidates:
                raise SourceError("authority_changed")
            now = datetime.now(UTC)
            expires = now + timedelta(minutes=15)
            payload = request.model_dump(mode="json")
            payload["connection_revision"] = grant.revision
            # Retain only the chosen ancestry; cross-owner candidate metadata stays private and transient.
            payload["ancestry"] = list(proof.ancestors(request.root_id))
            payload["proof_sha256"] = hashlib.sha256(
                json.dumps(asdict(proof), sort_keys=True).encode()
            ).hexdigest()
            digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            identifier = str(uuid4())
            await self.records.save(
                SourceMapping(
                    id=identifier,
                    tenant_id=tenant,
                    owner=actor,
                    connection_id=row.id,
                    provider=row.provider,
                    external_subject=account.subject,
                    external_tenant=account.tenant_id,
                    issuer=row.issuer,
                    config_fingerprint=row.config_fingerprint,
                    drive_id=request.drive_id,
                    root_id=request.root_id,
                    workspace_id=request.destination.workspace_id,
                    project_id=request.destination.project_id,
                    parent_id=request.destination.parent_id,
                    request_json=payload,
                    request_sha256=digest,
                    status="reviewed",
                    revision=1,
                    reviewed_at=now,
                    reviewed_expires_at=expires,
                )
            )
            return MappingReviewOutput(id=identifier, revision=1, expires_at=expires)

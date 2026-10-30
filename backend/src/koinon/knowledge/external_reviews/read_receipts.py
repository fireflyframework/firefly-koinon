# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Append-only seals of actual MCP source reads, scoped to the credential that read them."""

import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional

from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import TenantRepository
from koinon.catalog.service import CatalogService
from koinon.evidence.dtos import SourceReference
from koinon.evidence.ports import SourceResolverPort
from koinon.knowledge.capture_dtos import CapturedEvidence
from koinon.knowledge.curated.authority import digest
from koinon.knowledge.external_reviews.read_receipt_entities import ExternalReadReceiptRow
from koinon.knowledge.external_reviews.read_receipt_ports import ExternalReadReceiptPort
from koinon.knowledge.external_reviews.read_receipt_repositories import ExternalReadReceiptRepository
from koinon.knowledge.external_reviews.read_receipt_settings import ExternalReadReceiptSettings
from koinon.knowledge.external_reviews.service import fingerprint
from koinon.tokens.authorization import TokenRestriction


def not_recorded(reason: str) -> dict:
    return {"status": "not_recorded", "reason": reason, "sources": []}


def sealed(row: ExternalReadReceiptRow) -> dict:
    return {
        name: getattr(row, name)
        for name in (
            "id",
            "tenant_id",
            "subject",
            "credential_id",
            "application_id",
            "credential_sha256",
            "operation",
            "request_sha256",
            "result_sha256",
            "sources_json",
            "provenance_json",
        )
    } | {"created_at": row.created_at.isoformat(), "expires_at": row.expires_at.isoformat()}


@service(name="knowledge.external_reviews.read_receipts")
class ExternalReadReceipts(ExternalReadReceiptPort):
    def __init__(
        self,
        receipts: ExternalReadReceiptRepository,
        tokens: TokenRestriction,
        catalog: CatalogService,
        tenants: TenantRepository,
        sources: Provider[SourceResolverPort | None],
        settings: ExternalReadReceiptSettings,
    ):
        self.receipts, self.tokens, self.catalog, self.tenants, self.sources, self.settings = (
            receipts,
            tokens,
            catalog,
            tenants,
            sources,
            settings,
        )
        settings.validate()

    async def grant(self, subject, tenant_id):
        grant = await self.tokens.grant(subject)
        if grant is None or grant.tenant_id != tenant_id:
            raise AccessDenied("An active external credential is required", code="TOKEN_UNAVAILABLE")
        return grant

    async def authorize(self, subject, tenant_id, sources):
        resolver = self.sources.get()
        if resolver is None:
            raise AccessDenied("Exact read provenance is unavailable", code="MCP_READ_RECEIPT_UNAVAILABLE")
        for source in sources:
            row = await self.catalog.get(subject, tenant_id, source.asset_id)
            permission = (
                "knowledge:search" if source.kind in {"document", "knowledge_version"} else "query:execute"
            )
            await self.catalog.authorize(subject, tenant_id, permission, row.workspace_id)
            if self.catalog.restriction:
                await self.catalog.restriction.resource(subject, row)
        current = await resolver.resolve(subject, tenant_id, sources)
        if len(current) != len(sources) or any(
            actual.id != used.id
            or actual.used_revision != used.used_revision
            or actual.availability != "available"
            or actual.current_revision != used.used_revision
            for used, actual in zip(sources, current, strict=True)
        ):
            raise AccessDenied(
                "A read source changed; retrieve it again", code="MCP_READ_RECEIPT_UNAVAILABLE"
            )

    @transactional
    async def record(
        self, subject: str, tenant_id: str, operation: str, arguments: dict, capture: CapturedEvidence
    ) -> dict:
        grant = await self.grant(subject, tenant_id)
        if operation not in {"search", "query", "fetch"} or not capture.complete or not capture.sources:
            return not_recorded("incomplete_or_unsupported_source_manifest")
        if len(capture.sources) > 64 or any(not value.used_revision for value in capture.sources):
            return not_recorded("source_manifest_limit_or_missing_revision")
        await self.authorize(subject, tenant_id, capture.sources)
        now = datetime.now(UTC)
        row = ExternalReadReceiptRow(
            id=secrets.token_urlsafe(32),
            tenant_id=tenant_id,
            subject=subject,
            credential_id=grant.id,
            application_id=grant.authorized_application_id,
            credential_sha256=fingerprint(grant),
            operation=operation,
            request_sha256=digest(arguments),
            result_sha256=digest(capture.data),
            sources_json=[v.model_dump(mode="json") for v in capture.sources],
            provenance_json={
                "native_reads": [asdict(v) for v in capture.native_reads],
                "sql_attempts": [asdict(v) for v in capture.sql_attempts],
                "rlm_tools": None
                if capture.rlm_tools is None
                else [value.model_dump(mode="json") for value in capture.rlm_tools],
            },
            created_at=now,
            expires_at=min(grant.expires_at, now + timedelta(seconds=self.settings.ttl_seconds)),
        )
        manifest = sealed(row)
        if (
            len(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode())
            > self.settings.max_receipt_bytes
        ):
            return not_recorded("receipt_byte_limit")
        await self.tenants.find_by_id(tenant_id, lock=LockMode.PESSIMISTIC_WRITE)
        if await self.receipts.active_count(tenant_id, subject, now) >= self.settings.max_active_receipts:
            return not_recorded("active_receipt_limit")
        row.receipt_sha256 = digest(manifest)
        await self.receipts.save(row)
        return {
            "status": "recorded",
            "id": row.id,
            "sha256": row.receipt_sha256,
            "expires_at": row.expires_at.isoformat(),
            "sources": row.sources_json,
        }

    async def resolve(
        self, subject: str, tenant_id: str, receipt_ids: tuple[str, ...]
    ) -> tuple[tuple[SourceReference, ...], tuple[str, ...]]:
        if not 1 <= len(receipt_ids) <= 32 or len(set(receipt_ids)) != len(receipt_ids):
            raise AccessDenied(
                "Select at most 32 distinct read receipts", code="MCP_READ_RECEIPT_UNAVAILABLE"
            )
        grant = await self.grant(subject, tenant_id)
        sources = {}
        for identifier in receipt_ids:
            row = await self.receipts.find_by_id(identifier)
            if (
                row is None
                or (row.tenant_id, row.subject, row.credential_id, row.application_id, row.credential_sha256)
                != (tenant_id, subject, grant.id, grant.authorized_application_id, fingerprint(grant))
                or row.expires_at <= datetime.now(UTC)
            ):
                raise AccessDenied(
                    "Read receipt expired or is unavailable; retrieve sources again",
                    code="MCP_READ_RECEIPT_UNAVAILABLE",
                )
            if not secrets.compare_digest(row.receipt_sha256, digest(sealed(row))):
                raise AccessDenied("Read receipt integrity failed", code="MCP_READ_RECEIPT_UNAVAILABLE")
            for value in row.sources_json:
                source = SourceReference.model_validate(value)
                if source.id in sources and sources[source.id] != source:
                    raise AccessDenied(
                        "Read receipt source identity conflicts", code="MCP_READ_RECEIPT_UNAVAILABLE"
                    )
                sources[source.id] = source
        if len(sources) > 499:
            raise AccessDenied("Narrow the selected evidence", code="MCP_READ_RECEIPT_UNAVAILABLE")
        result = tuple(sources.values())
        await self.authorize(subject, tenant_id, result)
        return result, (grant.id,)

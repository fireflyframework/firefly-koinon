# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from pyfly.container import service
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import select

from koinon.catalog.ancestry import MAX_FOLDER_ANCESTRY, validated_ancestry
from koinon.catalog.entities import CatalogEntry
from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.catalog.service import PARENTS, ROLE_PERMISSIONS, CatalogService
from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.ports import SourceIntakeAdmission
from koinon.knowledge.bulk.repositories import BulkRepository


@dataclass(frozen=True, slots=True)
class SourceDestinationIdentity:
    id: str
    tenant_id: str
    kind: str
    parent_id: str | None
    workspace_id: str | None
    project_id: str | None
    status: str


def execution_context(subject: str, token_id: str | None) -> SecurityContext:
    if not isinstance(subject, str) or not 3 <= len(subject) <= 512:
        raise ConflictException("Queued origin is unresolved", code="INGEST_EXECUTION_CONTEXT_REQUIRED")
    issuer, separator, external_subject = subject.partition("|")
    if not separator or not issuer or not external_subject:
        raise ConflictException("Queued origin is unresolved", code="INGEST_EXECUTION_CONTEXT_REQUIRED")
    attributes = {"iss": issuer, "sub": external_subject}
    if token_id is not None:
        if not isinstance(token_id, str) or not 1 <= len(token_id) <= 64:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        attributes["koinon_token_id"] = token_id
    return SecurityContext(user_id=external_subject, attributes=attributes)


def token_identity() -> str | None:
    context = SecurityContextHolder.get_context()
    token = context.attributes.get("koinon_token_id") if context else None
    if token is not None and (not isinstance(token, str) or not 1 <= len(token) <= 64):
        raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
    return token


@service(name="knowledge.bulk.authority")
class BulkAuthority:
    def __init__(self, catalog: CatalogService, records: BulkRepository):
        self.catalog, self.records = catalog, records

    async def source_item(self, admission: SourceIntakeAdmission, batch, item) -> None:
        """Exact initial-intake identities for a producer that already owns its source fence."""
        from koinon.integrations.content_sources.import_entities import SourceImportAttempt
        from koinon.integrations.content_sources.sync_entities import SourceImportedAsset

        session = self.records._require_session()
        if len(admission.items) != 1:
            raise AccessDenied("Source intake identity differs", code="ACCESS_DENIED")
        pin = admission.items[0]
        attempt = await session.scalar(
            select(SourceImportAttempt.id)
            .join(
                SourceImportedAsset,
                SourceImportedAsset.initial_attempt_id == SourceImportAttempt.id,
            )
            .where(
                SourceImportAttempt.tenant_id == admission.tenant_id,
                SourceImportAttempt.mapping_id == admission.mapping_id,
                SourceImportAttempt.object_id == pin.object_id,
                SourceImportAttempt.generation == pin.generation,
                SourceImportAttempt.intake_item_id == item.id,
                SourceImportAttempt.source_id == item.source_id,
                SourceImportAttempt.asset_id == item.asset_id,
                SourceImportAttempt.sha256 == item.sha256,
                SourceImportAttempt.size_bytes == item.size_bytes,
                SourceImportedAsset.tenant_id == admission.tenant_id,
                SourceImportedAsset.source_id == item.source_id,
                SourceImportedAsset.asset_id == item.asset_id,
            )
        )
        rows = (
            await session.execute(
                select(
                    CatalogEntry.id,
                    CatalogEntry.parent_id,
                    CatalogEntry.kind,
                    CatalogEntry.status,
                    CatalogEntry.workspace_id,
                    CatalogEntry.project_id,
                    CatalogEntry.metadata_json["sha256"].as_string(),
                )
                .where(
                    CatalogEntry.tenant_id == admission.tenant_id,
                    CatalogEntry.id.in_((item.source_id, item.asset_id)),
                )
                .order_by(CatalogEntry.id)
            )
        ).all()
        local = {row.id: row for row in rows}
        source, asset = local.get(item.source_id), local.get(item.asset_id)
        if (
            attempt is None
            or source is None
            or asset is None
            or item.batch_id != batch.id
            or item.ordinal != 0
            or source.kind != "source"
            or asset.kind != item.mode
            or source.parent_id != admission.destination[2]
            or asset.parent_id != source.id
            or any(
                (row.workspace_id, row.project_id) != admission.destination[:2]
                or row.status != "pending"
                or row[6] != item.sha256
                for row in rows
            )
        ):
            raise AccessDenied("Source intake identity differs", code="ACCESS_DENIED")

    async def source_destination(self, admission: SourceIntakeAdmission) -> None:
        """Private producer authority; no reader permission or protected catalog output is granted."""
        subject, tenant = admission.owner, admission.tenant_id
        token = token_identity()
        if token and self.catalog.restriction is None:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        await self.records.authority_lock(tenant, subject, token)
        session = self.records._require_session()
        observed: dict[str, SourceDestinationIdentity] = {}

        async def read(identifier: str) -> SourceDestinationIdentity:
            if identifier not in observed:
                row = (
                    await session.execute(
                        select(
                            CatalogEntry.id,
                            CatalogEntry.tenant_id,
                            CatalogEntry.kind,
                            CatalogEntry.parent_id,
                            CatalogEntry.workspace_id,
                            CatalogEntry.project_id,
                            CatalogEntry.status,
                        ).where(CatalogEntry.tenant_id == tenant, CatalogEntry.id == identifier)
                    )
                ).one_or_none()
                if row is None:
                    raise AccessDenied("Source destination is unavailable", code="ACCESS_DENIED")
                observed[identifier] = SourceDestinationIdentity(*row)
            return observed[identifier]

        parent = await read(admission.destination[2])
        try:
            chain = await validated_ancestry(parent, read, PARENTS)
        except InvalidHierarchy:
            raise AccessDenied("Source destination is unavailable", code="ACCESS_DENIED") from None
        if (
            parent.kind not in {"collection", "corpus"}
            or not 3 <= len(chain) <= MAX_FOLDER_ANCESTRY
            or (chain[-1].id, chain[-2].id) != admission.destination[:2]
            or chain[-2].kind != "project"
        ):
            raise AccessDenied("Source destination ancestry differs", code="ACCESS_DENIED")
        # The tenant lock serializes catalog mutations; lock ancestor rows in stable ID order too.
        await session.execute(
            select(CatalogEntry.id)
            .where(
                CatalogEntry.tenant_id == tenant,
                CatalogEntry.id.in_(sorted(observed)),
            )
            .order_by(CatalogEntry.id)
            .with_for_update(read=True)
        )
        for permission in ("catalog:write", "ingest:write"):
            await self.catalog.authorize(subject, tenant, permission, admission.destination[0])
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, parent, write=True, parent_reader=read)

    async def read_bounds(self, subject: str, tenant: str) -> dict:
        if token_identity() and self.catalog.restriction is None:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        memberships = [
            member
            for member in await self.catalog.memberships(subject)
            if member.tenant_id == tenant and "catalog:read" in ROLE_PERMISSIONS.get(member.role, ())
        ]
        if not memberships:
            raise AccessDenied("Bulk history is unavailable", code="ACCESS_DENIED")
        allowed = (
            None
            if any(m.workspace_id is None for m in memberships)
            else [m.workspace_id for m in memberships]
        )
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        if grant is not None:
            if grant.tenant_id != tenant or "catalog:read" not in grant.scopes:
                raise AccessDenied("Bulk history exceeds token scope", code="TOKEN_SCOPE_DENIED")
            if grant.workspace_ids is not None:
                allowed = (
                    grant.workspace_ids
                    if allowed is None
                    else sorted(set(allowed) & set(grant.workspace_ids))
                )
        return {
            "allowed_workspaces": allowed,
            "allowed_assets": grant.asset_ids if grant else None,
            "allowed_resources": grant.resource_ids if grant else None,
        }

    async def destination(
        self, subject: str, tenant: str, target: BulkDestination, *, write: bool
    ) -> tuple[CatalogEntry, ...]:
        token = token_identity()
        if token and self.catalog.restriction is None:
            raise AccessDenied("Original token cannot be verified", code="TOKEN_UNAVAILABLE")
        if write:
            await self.records.authority_lock(tenant, subject, token)
        # Catalog creation/movement/archive serialize on this same tenant before changing ancestry.
        rows = await self.catalog.catalog_repository.ancestry_rows(tenant, (target.parent_id,), fresh=True)
        observed = {row.id: row for row in rows}
        if write:
            await self.records.catalog_locks(tenant, tuple(sorted(observed)))

        async def read(identifier: str) -> CatalogEntry:
            if identifier not in observed:
                raise AccessDenied("Bulk destination is unavailable", code="ACCESS_DENIED")
            return await self.catalog.get(subject, tenant, identifier)

        parent = await read(target.parent_id)
        try:
            chain = await validated_ancestry(parent, read, PARENTS)
        except InvalidHierarchy:
            raise AccessDenied("Bulk destination is unavailable", code="ACCESS_DENIED") from None
        if (
            parent.kind not in {"collection", "corpus"}
            or not 3 <= len(chain) <= MAX_FOLDER_ANCESTRY
            or chain[-1].id != target.workspace_id
            or chain[-2].id != target.project_id
            or chain[-2].kind != "project"
        ):
            raise AccessDenied("Bulk destination ancestry differs", code="ACCESS_DENIED")
        if write:
            for permission in ["catalog:write", "ingest:write"]:
                await self.catalog.authorize(subject, tenant, permission, target.workspace_id)
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, parent, write=write)
        return tuple(chain)

    async def item(
        self, subject: str, tenant: str, source_id: str, asset_id: str, target: BulkDestination, digest: str
    ) -> None:
        await self.records.catalog_locks(tenant, (source_id, asset_id))
        source = await self.catalog.get(subject, tenant, source_id)
        asset = await self.catalog.get(subject, tenant, asset_id)
        if (
            source.kind != "source"
            or source.parent_id != target.parent_id
            or asset.parent_id != source.id
            or asset.kind not in {"document", "dataset"}
            or any(
                row.workspace_id != target.workspace_id
                or row.project_id != target.project_id
                or row.status == "archived"
                for row in [source, asset]
            )
            or source.metadata_json.get("sha256") != digest
            or asset.metadata_json.get("sha256") != digest
        ):
            raise AccessDenied(
                "Reserved intake source changed or was archived", code="BULK_DESTINATION_CHANGED"
            )
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, asset, write=True)

    async def dataset(self, subject: str, tenant: str, item, target: BulkDestination) -> None:
        reservation = DatasetReservation.stored(item.reservation_json)
        tables = await self.records.table_reservations(item.id)
        if len(tables) > reservation.max_tables:
            raise AccessDenied("Reserved tables exceed admission", code="BULK_DESTINATION_CHANGED")
        await self.records.catalog_locks(
            tenant, (reservation.catalog_file_version_id, *(row.catalog_table_id for row in tables))
        )
        version = await self.catalog.get(subject, tenant, reservation.catalog_file_version_id)
        if (
            version.kind != "index_version"
            or version.parent_id != item.asset_id
            or version.workspace_id != target.workspace_id
            or version.project_id != target.project_id
            or version.status == "archived"
            or version.metadata_json.get("bulk_item_id") != item.id
            or version.metadata_json.get("sha256") != item.sha256
            or version.metadata_json.get("bytes") != item.size_bytes
        ):
            raise AccessDenied("Reserved file version changed", code="BULK_DESTINATION_CHANGED")
        for row in tables:
            table = await self.catalog.get(subject, tenant, row.catalog_table_id)
            if (
                table.kind != "table"
                or table.parent_id != item.asset_id
                or table.name != row.name
                or table.workspace_id != target.workspace_id
                or table.project_id != target.project_id
                or table.status == "archived"
                or table.metadata_json.get("bulk_item_id") != item.id
                or table.metadata_json.get("snapshot_id") != row.snapshot_id
            ):
                raise AccessDenied("Reserved table changed", code="BULK_DESTINATION_CHANGED")
            if self.catalog.restriction:
                await self.catalog.restriction.resource(subject, table, write=True)
        if self.catalog.restriction:
            await self.catalog.restriction.resource(subject, version, write=True)

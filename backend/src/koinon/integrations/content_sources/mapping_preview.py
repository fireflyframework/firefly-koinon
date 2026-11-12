# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded, freshly authorized previews show the exact native import choice."""

import asyncio
import hashlib
import json
import unicodedata
from dataclasses import asdict, dataclass

from pyfly.container import service
from pyfly.kernel import ConflictException
from sqlalchemy import select

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.browse import PersonalSourceBrowser
from koinon.integrations.content_sources.dtos import RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.google_drive import _EXPORTS
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.lifecycle import SourceConnectionService, _no_remote_unit
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceObject
from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.sync_entities import SourceFolderBinding, SourceImportedAsset
from koinon.integrations.content_sources.sync_walk import walk_page
from koinon.knowledge.bulk.authority import BulkAuthority
from koinon.knowledge.bulk.dtos import FileManifestItem
from koinon.knowledge.bulk.upload_formats import upload_formats
from koinon.security.authority import primary_authority

_EXTENSIONS = {
    "application/vnd.google-apps.document": ".docx",
    "application/vnd.google-apps.spreadsheet": ".xlsx",
    "application/vnd.google-apps.presentation": ".pptx",
}


@dataclass(frozen=True, slots=True)
class ImportChoice:
    filename: str
    export_mime: str | None
    reason: str | None


def import_choice(item: RemoteItem, policy: MappingReviewInput, available: set[str]) -> ImportChoice:
    extension = _EXTENSIONS.get(item.mime_type)
    filename = item.name + extension if extension and not item.name.lower().endswith(extension) else item.name
    export_mime = _EXPORTS.get(item.mime_type)
    reason = None
    try:
        FileManifestItem.plain_filename(filename)
        if not 1 <= len(filename) <= 255:
            raise ValueError
    except ValueError:
        reason = "SOURCE_NAME_UNSUPPORTED"
    if reason is None:
        if item.kind == "folder" and item.version is not None:
            reason = "SOURCE_HIERARCHY_FLATTENED" if policy.hierarchy == "flatten" else None
        elif item.kind != "file" or item.version is None:
            reason = "SOURCE_FORMAT_UNSUPPORTED"
        elif item.can_download is False:
            reason = "SOURCE_DOWNLOAD_DENIED"
        elif not any(filename.lower().endswith(ext) for ext in policy.formats):
            reason = "SOURCE_FORMAT_UNSELECTED"
        elif not any(filename.lower().endswith(ext) for ext in available):
            reason = "SOURCE_PARSER_UNAVAILABLE"
    return ImportChoice(filename, export_mime, reason)


def source_name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name.strip()).casefold()


def preview_collisions(entries, hierarchy):
    keys = set()
    duplicates = 0
    for item in entries:
        if item["kind"] not in {"file", "folder"} or item["reason"] is not None:
            continue
        parts = [item["filename"]] if hierarchy == "flatten" else item["relative_path"]
        key = tuple(source_name_key(part) for part in parts)
        duplicates += key in keys
        keys.add(key)
    return duplicates


def source_preview_paths(entries, hierarchy):
    groups = {}
    for item in entries:
        path = [item["filename"]] if hierarchy == "flatten" else item["relative_path"]
        item["destination_relative_path"] = [part.strip() for part in path]
        item["collision"] = "none"
        if item["reason"] is None and item["kind"] in {"file", "folder"}:
            groups.setdefault(tuple(source_name_key(part) for part in path), []).append(item)
    for group in groups.values():
        if len(group) > 1:
            for item in group:
                item["collision"] = "source_name"


def available_extensions(mode):
    return {
        extension
        for format in upload_formats()
        if format.mode == mode and format.available
        for extension in format.extensions
    }


@dataclass(frozen=True, slots=True)
class CapturedPreview:
    connection_revision: int
    items: tuple[dict, ...]
    complete: bool
    collisions: int
    sha256: str


@service(name="content_sources.mapping_preview")
class SourceMappingPreview:
    def __init__(
        self, authority: BulkAuthority, connections: SourceConnectionService, browser: PersonalSourceBrowser
    ):
        self.authority, self.connections, self.browser = authority, connections, browser

    async def capture(
        self, actor: str, tenant: str, request: MappingReviewInput, *, mapping_id=None
    ) -> CapturedPreview:
        _no_remote_unit()
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self.authority.destination(actor, tenant, request.destination, write=True)
        connection = await self.connections.connected(actor, tenant, request.connection_id)
        account = connection.account
        if account is None:
            raise SourceError("reconnect_required")
        grant = await self.connections.read_grant(actor, tenant, request.connection_id, account)
        scope = SourceScope(account, request.drive_id)
        available = available_extensions(request.mode)
        entries, complete, state = [], False, None
        names = {}
        try:
            async with (
                asyncio.timeout(120),
                self.browser._source(scope, _OperationToken(account, grant.token)) as adapter,
            ):
                before = await FolderAncestry(adapter, scope).capture((request.root_id,))
                observed = []
                for _ in range(10):
                    page = await walk_page(
                        adapter,
                        scope,
                        request.root_id,
                        recursive=request.recursive,
                        excluded=tuple(request.excluded_ids),
                        state=state,
                    )
                    remaining = 100 - len(entries)
                    truncated = len(page.items) > remaining
                    for entry in page.items[:remaining]:
                        item = entry.item
                        choice = import_choice(item, request, available)
                        names[item.item_id] = item.name
                        entries.append(
                            {
                                "item_id": item.item_id,
                                "name": item.name,
                                "kind": item.kind,
                                "version": item.version,
                                "filename": choice.filename,
                                "export_mime": choice.export_mime,
                                "reason": choice.reason,
                                "ancestry": list(entry.ancestry),
                                "relative_path": [
                                    *(names[parent] for parent in entry.ancestry[1:]),
                                    choice.filename,
                                ],
                                "size_bytes": item.size_bytes,
                            }
                        )
                        observed.append(item)
                    complete = page.complete and not truncated
                    if page.complete or len(entries) == 100:
                        break
                    state = page.next_state
                slots = asyncio.Semaphore(4)

                async def confirm(item):
                    async with slots:
                        if await adapter.get_item(item.item_id) != item:
                            raise SourceError("version_changed")

                await asyncio.gather(*(confirm(item) for item in observed))
                if await FolderAncestry(adapter, scope).capture((request.root_id,)) != before:
                    raise SourceError("authority_changed")
        except TimeoutError:
            raise SourceError("timeout") from None
        await self.connections.confirm_read_grant(actor, tenant, request.connection_id, grant)
        await self.authority.catalog._refresh_managed_memberships(actor)
        async with primary_authority(read_only=False):
            await self.authority.destination(actor, tenant, request.destination, write=True)
            await self.local_conflicts(actor, tenant, request, entries, mapping_id=mapping_id)
        collisions = sum(item["collision"] != "none" for item in entries)
        payload = {
            "items": entries,
            "complete": complete,
            "collisions": collisions,
            "root_proof": asdict(before),
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return CapturedPreview(grant.revision, tuple(entries), complete, collisions, digest)

    async def local_conflicts(self, actor, tenant, request, entries, *, mapping_id=None):
        """Check the bounded proposed namespace under canonical authority and its tenant lock."""
        source_preview_paths(entries, request.hierarchy)
        session = self.authority.records._require_session()
        folders, origins, sources = {}, {}, {}
        if mapping_id is not None:
            relevant = {identifier for item in entries for identifier in (*item["ancestry"], item["item_id"])}
            folders = {
                row.remote_folder_id: row.local_folder_id
                for row in (
                    await session.scalars(
                        select(SourceFolderBinding).where(
                            SourceFolderBinding.tenant_id == tenant,
                            SourceFolderBinding.mapping_id == mapping_id,
                            SourceFolderBinding.remote_folder_id.in_(relevant),
                        )
                    )
                ).all()
            }
            origins = {
                row.item_id: row
                for row in (
                    await session.scalars(
                        select(SourceObject).where(
                            SourceObject.tenant_id == tenant,
                            SourceObject.mapping_id == mapping_id,
                            SourceObject.item_id.in_([item["item_id"] for item in entries]),
                        )
                    )
                ).all()
            }
            sources = dict(
                (
                    await session.execute(
                        select(SourceImportAttempt.object_id, SourceImportedAsset.source_id)
                        .join(
                            SourceImportedAsset,
                            SourceImportedAsset.initial_attempt_id == SourceImportAttempt.id,
                        )
                        .where(
                            SourceImportAttempt.tenant_id == tenant,
                            SourceImportAttempt.mapping_id == mapping_id,
                            SourceImportAttempt.object_id.in_([origin.id for origin in origins.values()]),
                        )
                    )
                ).all()
            )
        parents = {request.destination.parent_id, *folders.values()}
        siblings = (
            await session.execute(
                select(
                    CatalogEntry.id,
                    CatalogEntry.parent_id,
                    CatalogEntry.name,
                    CatalogEntry.mutation_revision,
                )
                .where(CatalogEntry.tenant_id == tenant, CatalogEntry.parent_id.in_(parents))
                .limit(100001)
            )
        ).all()
        if len(siblings) > 100000:
            raise SourceError("size_exceeded")
        indexed = {}
        for sibling in siblings:
            indexed.setdefault((sibling.parent_id, source_name_key(sibling.name)), []).append(sibling)
        checked = set()
        for item in entries:
            if item["reason"] is not None or item["kind"] not in {"file", "folder"}:
                continue
            selected_file = item["kind"] == "file" and item["item_id"] == request.root_id
            if not item["ancestry"] and not selected_file:
                raise SourceError("scope_mismatch")
            remote_parent = item["ancestry"][-1] if item["ancestry"] else None
            parent = (
                request.destination.parent_id
                if selected_file or request.hierarchy == "flatten" or remote_parent == request.root_id
                else folders.get(remote_parent)
            )
            if parent is None:
                continue
            origin = origins.get(item["item_id"])
            owned = (
                folders.get(item["item_id"])
                if item["kind"] == "folder"
                else sources.get(origin.id)
                if origin
                else None
            )
            if origin is not None and owned is not None and item["kind"] == "file":
                try:
                    await SourcePublicationBaselines(session).current_origin(
                        tenant, mapping_id,
                        (request.destination.workspace_id, request.destination.project_id), origin,
                    )
                except ConflictException:
                    item["collision"] = "local_edit"
            for sibling in indexed.get((parent, source_name_key(item["filename"])), ()):
                if sibling.id not in checked:
                    # A generic denial is preferable to revealing a protected conflict.
                    await self.authority.catalog.get(actor, tenant, sibling.id)
                    checked.add(sibling.id)
                if sibling.id != owned:
                    item["collision"] = "destination_name"
                elif (
                    origin is not None and item["kind"] == "folder"
                    and origin.published_local_revision != str(sibling.mutation_revision)
                ):
                    item["collision"] = "local_edit"

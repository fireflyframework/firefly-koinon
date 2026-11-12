# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded reader-aware catalog projection with opaque, non-authorizing cursors."""

import hashlib
import json

from pyfly.cache.ports.outbound import CacheAdapter
from pyfly.container import Provider, service

from koinon.catalog.browse_dtos import CatalogBrowseInput, CatalogBrowseOutput
from koinon.catalog.dtos import CatalogEntryOutput, CatalogSummary
from koinon.catalog.errors import AccessDenied
from koinon.catalog.mappers import entry_dto
from koinon.catalog.service import CatalogService
from koinon.catalog.summaries import entry_format, summary
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_cursors import SourceBrowseCursors
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.profiles.service import ProfileService


@service(name="catalog.reader_browse")
class CatalogBrowse:
    def __init__(
        self,
        catalog: CatalogService,
        reader: SourceReader,
        cache: Provider[CacheAdapter | None] | None = None,
        profiles: Provider[ProfileService | None] | None = None,
    ):
        self.catalog, self.reader, self.cache, self.profiles = catalog, reader, cache, profiles

    async def page(self, actor: str, tenant: str, request: CatalogBrowseInput) -> CatalogBrowseOutput:
        cursors = SourceBrowseCursors(self.cache)
        profiles = self.profiles.get() if isinstance(self.profiles, Provider) else self.profiles
        operation = await self.reader.begin(actor, tenant, request.reader_source_connections)
        filters = request.model_dump(exclude={"cursor", "reader_source_connections"})
        binding = hashlib.sha256(
            json.dumps(
                {
                    "actor": actor,
                    "tenant": tenant,
                    "filters": filters,
                    "selection_revision": operation.selection.revision,
                    "selections": [
                        value.model_dump(mode="json") for value in operation.selection.connections
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        position = await cursors.read(actor, tenant, binding, request.cursor)
        if request.parent_id:
            await self.reader.entries(actor, tenant, (request.parent_id,), operation=operation)
        scan_filters = {**filters, "q": "", "status": None, "format": None, "tag": None}
        page = await self.catalog.page(
            actor, tenant, **scan_filters, page=position, _include_imported=True, _identities_only=True
        )
        admitted = []
        for identifier in page["items"]:
            try:
                await self.reader.entries(actor, tenant, (identifier,), operation=operation)
            except SourceError as error:
                if error.code == "size_exceeded":
                    raise
                continue
            except AccessDenied:
                continue
            admitted.append(identifier)
        entries = []
        await operation.release()
        async with operation.read_fence():
            for identifier in admitted:
                entry = await self.catalog.get(actor, tenant, identifier)
                if self._matches(entry, request):
                    entries.append(entry)
        entries.sort(
            key=lambda entry: (
                getattr(entry, request.sort).casefold()
                if request.sort in {"name", "kind"}
                else getattr(entry, request.sort),
                entry.id,
            ),
            reverse=request.order == "desc",
        )
        actors = (
            await profiles.author_summaries(
                {subject for entry in entries for subject in (entry.created_by, entry.updated_by) if subject},
                actor=actor,
                tenant_id=tenant,
                workspace_id=request.workspace_id,
            )
            if entries and profiles is not None
            else {}
        )
        await operation.release()
        cursor = None
        if page["scan_full"]:
            cursor = await cursors.issue(actor, tenant, binding, position + 1)
        async with operation.read_fence():
            return CatalogBrowseOutput(
                items=[CatalogEntryOutput.model_validate(entry_dto(entry)) for entry in entries],
                actors=actors,
                summaries={
                    entry.id: CatalogSummary.model_validate(summary(entry, None, entry_format(entry)))
                    for entry in entries
                },
                next_cursor=cursor,
            )

    @staticmethod
    def _matches(entry, request):
        from koinon.catalog.summaries import entry_format

        metadata = entry.metadata_json or {}
        tags = metadata.get("tags", [])
        tags = {tag for tag in tags if isinstance(tag, str)} if isinstance(tags, list) else set()
        language = metadata.get("language")
        if isinstance(language, str):
            tags.add(language)
        return (
            (not request.q or request.q.casefold() in entry.name.casefold())
            and (request.status is None or request.status == entry.status)
            and (request.format is None or request.format == entry_format(entry))
            and (request.tag is None or request.tag in tags)
        )

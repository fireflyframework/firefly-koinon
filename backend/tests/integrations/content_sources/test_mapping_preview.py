# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from pyfly.data.transaction import current_unit_of_work
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_review import review as review

from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.dtos import Account, Cursor, ItemPage, RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_preview import (
    SourceMappingPreview,
    import_choice,
    preview_collisions,
)
from koinon.security.authority import primary_authority


def request():
    return MappingReviewInput(
        connection_id="connection",
        drive_id="drive",
        root_id="root",
        recursive=True,
        removal_policy="retire",
        destination={"workspace_id": "workspace", "project_id": "project", "parent_id": "folder"},
        formats=[".docx", ".txt"],
    )


def item(name="report.txt", mime="text/plain"):
    return RemoteItem(
        SourceScope(Account("google_drive", "owner"), "drive"),
        "file",
        name,
        "file",
        "v1",
        7,
        mime,
        ("root",),
        True,
    )


def test_google_native_preview_uses_actual_export_extension_and_selected_formats():
    choice = import_choice(
        item("Report", "application/vnd.google-apps.document"), request(), {".docx", ".txt"}
    )
    assert choice.filename == "Report.docx" and choice.export_mime.endswith("wordprocessingml.document")
    assert choice.reason is None
    unavailable = import_choice(item("Report", "application/vnd.google-apps.document"), request(), {".txt"})
    assert unavailable.reason == "SOURCE_PARSER_UNAVAILABLE"


@pytest.mark.parametrize("left,right", [("Report.txt", " report.TXT "), ("Café.txt", "Cafe\u0301.txt")])
def test_source_collision_keys_match_canonical_stripping_and_unicode_case(left, right):
    entries = [{"kind": "file", "reason": None, "filename": name, "relative_path": [name]}
               for name in (left, right)]
    assert preview_collisions(entries, "preserve") == 1
    assert preview_collisions(entries, "flatten") == 1


def test_unsupported_names_shortcuts_and_permissions_remain_explicit():
    for value, reason in (
        (item("path/report.txt"), "SOURCE_NAME_UNSUPPORTED"),
        (replace(item(), kind="shortcut"), "SOURCE_FORMAT_UNSUPPORTED"),
        (replace(item(), can_download=False), "SOURCE_DOWNLOAD_DENIED"),
        (item("report.exe"), "SOURCE_FORMAT_UNSELECTED"),
    ):
        assert import_choice(value, request(), {".txt"}).reason == reason


def test_preserved_folders_need_no_file_parser_or_download_permission():
    folder = replace(item("Finance"), kind="folder", mime_type="folder", can_download=False)
    choice = import_choice(folder, request(), set())
    assert choice.reason is None and choice.filename == "Finance" and choice.export_mime is None
    assert import_choice(folder, request().model_copy(update={"hierarchy": "flatten"}), set()).reason == (
        "SOURCE_HIERARCHY_FLATTENED"
    )
    assert import_choice(replace(folder, version=None), request(), set()).reason == (
        "SOURCE_FORMAT_UNSUPPORTED"
    )


def test_flatten_collision_detection_uses_normalized_target_paths():
    entries = [
        {"relative_path": ["a", "Report.txt"], "filename": "Report.txt", "kind": "file", "reason": None},
        {"relative_path": ["b", "report.txt"], "filename": "report.txt", "kind": "file", "reason": None},
    ]
    assert preview_collisions(entries, "preserve") == 0
    assert preview_collisions(entries, "flatten") == 1


@pytest.mark.parametrize("hierarchy", ["preserve", "flatten"])
@pytest.mark.parametrize("occupied", [False, True])
async def test_selected_file_checks_destination_without_inventing_folder_ancestry(
    review, hierarchy, occupied
):
    selected = review.request.model_copy(update={"hierarchy": hierarchy, "recursive": False})
    if occupied:
        await review.context.get_bean(CatalogService).create(
            "issuer|alice", "tenant", kind="collection", name="report.txt",
            parent_id=selected.destination.parent_id,
        )
    entries = [{
        "item_id": selected.root_id, "kind": "file", "reason": None,
        "filename": "report.txt", "relative_path": ["report.txt"],
        "ancestry": [], "collision": "none",
    }]
    preview = SourceMappingPreview(
        review.service.authority, review.service.connections, review.service.browser
    )
    async with primary_authority(read_only=False):
        await preview.local_conflicts("issuer|alice", "tenant", selected, entries)
    assert entries[0]["collision"] == ("destination_name" if occupied else "none")
    assert entries[0]["ancestry"] == []


@pytest.mark.parametrize("excluded", [False, True])
async def test_verified_file_review_derives_effective_policy_without_mutating_creation(
    review, monkeypatch, excluded
):
    from pyfly.kernel import ConflictException

    original = review.service.browser._source

    @asynccontextmanager
    async def source(scope, token):
        async with original(scope, token) as adapter:
            get = adapter.get_item

            async def get_item(identifier):
                value = await get(identifier)
                return replace(value, kind="file") if identifier == "selected" else value

            adapter.get_item = get_item
            yield adapter

    monkeypatch.setattr(review.service.browser, "_source", source)
    creation = review.request.model_copy(update={"excluded_ids": ["other"] if excluded else []})
    before = creation.model_dump()
    if excluded:
        with pytest.raises(ConflictException) as failure:
            async with review.service.verified("issuer|alice", "tenant", creation):
                pytest.fail("A selected file cannot accept exclusions")
        assert failure.value.code == "SOURCE_INVALID_SELECTION"
    else:
        async with review.service.verified("issuer|alice", "tenant", creation) as (_, proof, payload, *_):
            assert payload["root_kind"] == "file" and payload["recursive"] is False
            assert payload["hierarchy"] == creation.hierarchy
            assert proof.root_kind("selected") == "file" and proof.ancestors("selected") == ("root",)
    assert creation.model_dump() == before


@pytest.mark.parametrize("changed,incomplete", [(False, False), (True, False), (False, True)])
async def test_preview_checks_each_item_after_enumeration_without_remote_database_units(
    review, monkeypatch, changed, incomplete
):
    original = review.service.browser._source

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:
            get = adapter.get_item
            remote = RemoteItem(
                scope, "document", "report.txt", "file", "v1", 7, "text/plain", ("selected",), True
            )
            remote_items = (
                tuple(replace(remote, item_id=f"document-{i}") for i in range(100))
                if incomplete
                else (remote,)
            )
            by_id = {value.item_id: value for value in remote_items}

            async def children(folder, cursor=None):
                assert folder == "selected" and cursor is None
                assert current_unit_of_work("primary") is None or current_unit_of_work("primary").completed
                return ItemPage(
                    remote_items, Cursor(scope, "children:selected", "later") if incomplete else None
                )

            async def get_item(identifier):
                if identifier in by_id:
                    return replace(by_id[identifier], version="v2") if changed else by_id[identifier]
                return await get(identifier)

            adapter.children, adapter.get_item = children, get_item
            yield adapter

    monkeypatch.setattr(review.service.browser, "_source", source)
    preview = SourceMappingPreview(
        review.service.authority, review.service.connections, review.service.browser
    )
    if changed:
        with pytest.raises(SourceError, match="version_changed"):
            await preview.capture("issuer|alice", "tenant", review.request)
    elif incomplete:
        captured = await preview.capture("issuer|alice", "tenant", review.request)
        assert not captured.complete and len(captured.items) == 100
    else:
        captured = await preview.capture("issuer|alice", "tenant", review.request)
        assert captured.complete and captured.items[0]["filename"] == "report.txt"

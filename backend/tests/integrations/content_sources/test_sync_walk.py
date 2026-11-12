# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.integrations.content_sources.dtos import Account, Cursor, ItemPage, RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.sync_walk import walk_page

SCOPE = SourceScope(Account("google_drive", "subject"), "drive")


def item(identifier, parent, kind="file"):
    return RemoteItem(SCOPE, identifier, identifier + ".txt", kind, "v1", 4, "text/plain", (parent,))


class Remote:
    def __init__(self, pages):
        self.pages = pages
        self.read = []

    async def children(self, folder, cursor=None):
        self.read.append(folder)
        return self.pages[(folder, cursor.token if cursor else None)]


async def test_walk_keeps_page_checkpoint_and_exclusion_subtrees_across_restart():
    remote = Remote(
        {
            ("root", None): ItemPage(
                (item("nested", "root", "folder"), item("private", "root", "folder")),
                Cursor(SCOPE, "children:root", "second"),
            ),
            ("root", "second"): ItemPage((item("document", "root"),), None),
            ("nested", None): ItemPage((item("child", "nested"),), None),
        }
    )
    first = await walk_page(remote, SCOPE, "root", recursive=True, excluded=("private",))
    assert first.complete is False
    second = await walk_page(
        remote, SCOPE, "root", recursive=True, excluded=("private",), state=first.next_state
    )
    third = await walk_page(
        remote, SCOPE, "root", recursive=True, excluded=("private",), state=second.next_state
    )
    assert [entry.item.item_id for entry in second.items] == ["document"]
    assert third.items[0].ancestry == ("root", "nested")
    assert third.complete is True and third.next_state is None
    assert "private" not in remote.read


async def test_nonrecursive_selection_does_not_enter_subfolders():
    remote = Remote({("root", None): ItemPage((item("nested", "root", "folder"),), None)})
    page = await walk_page(remote, SCOPE, "root", recursive=False, excluded=())
    assert page.complete and remote.read == ["root"]


async def test_cross_parent_or_repeated_folder_cannot_escape_selected_root():
    remote = Remote({("root", None): ItemPage((item("secret", "another-root"),), None)})
    with pytest.raises(SourceError):
        await walk_page(remote, SCOPE, "root", recursive=True, excluded=())


async def test_walk_counts_excluded_and_duplicate_observations_before_deduplication():
    public = item("public", "root")
    private = item("private", "root")
    folder = item("nested", "root", "folder")
    remote = Remote({("root", None): ItemPage((public, public, private, folder, folder), None)})
    page = await walk_page(remote, SCOPE, "root", recursive=True, excluded=("private",))
    assert page.raw_observed_count == 5
    assert [entry.item.item_id for entry in page.items] == ["public", "nested"]
    assert page.next_state["queue"] == [{"path": ["root", "nested"], "token": None}]


async def test_walk_rejects_changed_duplicate_even_when_item_is_excluded():
    from dataclasses import replace

    original = item("private", "root")
    remote = Remote({("root", None): ItemPage((original, replace(original, name="changed.txt")), None)})
    with pytest.raises(SourceError, match="version_changed"):
        await walk_page(remote, SCOPE, "root", recursive=True, excluded=("private",))


async def test_selected_file_is_one_observation_without_listing_its_parent():
    remote = Remote({})
    selected = item("chosen", "unselected-parent")
    page = await walk_page(remote, SCOPE, "chosen", recursive=True, excluded=(), chosen_root=selected)
    assert page.complete and page.next_state is None and page.raw_observed_count == 1
    assert [(entry.item, entry.ancestry) for entry in page.items] == [(selected, ())]
    assert remote.read == []
    with pytest.raises(SourceError, match="scope_mismatch"):
        await walk_page(remote, SCOPE, "different", recursive=True, excluded=(), chosen_root=selected)

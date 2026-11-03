# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded ancestry proofs never substitute an incomplete scan for no overlap."""

import pytest

from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_ancestry import FolderAncestry, overlaps

SCOPE = SourceScope(Account("google_drive", "owner"), "drive")


class Folders:
    def __init__(self, parents):
        self.parents = parents
        self.calls = []

    async def get_item(self, identifier):
        self.calls.append(identifier)
        return RemoteItem(
            SCOPE, identifier, "private title", "folder", "v1", None, "", parents=self.parents[identifier]
        )

    async def root(self):
        self.calls.append("root")
        return RemoteItem(SCOPE, "root", "private title", "folder", "v1", None, "", ())


async def test_shared_ancestors_read_once_per_pass_without_names_in_proof():
    source = Folders({"a": ("root",), "b": ("root",), "root": ()})
    proof = await FolderAncestry(source, SCOPE).capture(("a", "b"))
    assert source.calls == ["root", "a", "b"]
    assert "private title" not in repr(proof)
    assert proof.ancestors("a") == ("root",)


@pytest.mark.parametrize("parents", [{"a": ("a",)}, {"a": ("b",), "b": ("a",)}, {"a": ("b", "c")}])
async def test_cyclic_or_ambiguous_ancestry_fails_closed(parents):
    with pytest.raises(SourceError):
        await FolderAncestry(Folders(parents), SCOPE).capture(("a",))


async def test_review_bounds_reject_instead_of_returning_partial_proof():
    source = Folders({"a": ("b",), "b": ("root",), "root": ()})
    with pytest.raises(SourceError, match="size_exceeded"):
        await FolderAncestry(source, SCOPE, max_depth=2).capture(("a",))
    with pytest.raises(SourceError, match="size_exceeded"):
        await FolderAncestry(source, SCOPE, max_nodes=2).capture(("a",))
    with pytest.raises(SourceError, match="size_exceeded"):
        await FolderAncestry(source, SCOPE, max_roots=1).capture(("a", "b"))


async def test_missing_parent_is_not_accepted_as_a_new_drive_root():
    with pytest.raises(SourceError, match="access_denied"):
        await FolderAncestry(Folders({"a": ()}), SCOPE).capture(("a",))


@pytest.mark.parametrize("recursive,expected", [(False, False), (True, True)])
async def test_only_recursive_parent_overlaps_child(recursive, expected):
    proof = await FolderAncestry(Folders({"a": ("root",), "root": ()}), SCOPE).capture(("a", "root"))
    assert overlaps(proof, "root", recursive, "a", False) is expected
    assert overlaps(proof, "a", False, "root", recursive) is expected
    assert overlaps(proof, "a", False, "a", False)

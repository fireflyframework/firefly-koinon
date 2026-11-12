# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One bounded, resumable breadth-first page within an approved source root."""

from dataclasses import dataclass
from typing import Protocol

from koinon.integrations.content_sources.dtos import Cursor, ItemPage, RemoteItem, SourceScope, bounded
from koinon.integrations.content_sources.errors import SourceError


class ChildrenReader(Protocol):
    async def children(self, folder_id: str, cursor: Cursor | None = None) -> ItemPage: ...


@dataclass(frozen=True, slots=True)
class WalkItem:
    item: RemoteItem
    ancestry: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WalkPage:
    items: tuple[WalkItem, ...]
    next_state: dict | None
    complete: bool
    raw_observed_count: int


async def walk_page(
    reader: ChildrenReader,
    scope: SourceScope,
    root: str,
    *,
    recursive: bool,
    excluded: tuple[str, ...],
    state: dict | None = None,
    chosen_root: RemoteItem | None = None,
) -> WalkPage:
    """Read one provider page; callers encrypt checkpoints before storing them.

    A truncated or invalid listing never establishes scan completion. The bounded
    frontier fails closed when a tree needs more folders than this scan supports.
    """
    if chosen_root is not None:
        if chosen_root.scope != scope or chosen_root.item_id != root:
            raise SourceError("scope_mismatch")
        if chosen_root.kind == "file":
            if state is not None:
                raise SourceError("invalid_cursor")
            entries = () if root in excluded else (WalkItem(chosen_root, ()),)
            return WalkPage(entries, None, True, 1)
        if chosen_root.kind != "folder":
            raise SourceError("unsupported")
    selection = [root, recursive, sorted(set(excluded))]
    identity = [scope.account.provider, scope.account.subject, scope.account.tenant_id, scope.drive_id]
    try:
        bounded(root)
        if state is None:
            queue = [{"path": [root], "token": None}]
            seen = {root}
        else:
            if state.get("selection") != selection or state.get("identity") != identity:
                raise ValueError("Checkpoint selection changed")
            queue = state["queue"]
            raw_seen = state["seen"]
            if not isinstance(queue, list) or not 1 <= len(queue) <= 10000:
                raise ValueError("Invalid frontier")
            if not isinstance(raw_seen, list) or not 1 <= len(raw_seen) <= 10000:
                raise ValueError("Invalid visited folders")
            seen = {bounded(value) for value in raw_seen}
            queue = [dict(entry) for entry in queue]
            for entry in queue:
                path = entry["path"]
                if not isinstance(path, list) or not 1 <= len(path) <= 256 or path[0] != root:
                    raise ValueError("Invalid ancestry")
                if len(set(path)) != len(path) or any(bounded(value) not in seen for value in path):
                    raise ValueError("Invalid ancestry")
                if entry["token"] is not None:
                    bounded(entry["token"], limit=16384)
        current = queue.pop(0)
        path = tuple(current["path"])
        folder = path[-1]
        cursor = Cursor(scope, "children:" + folder, current["token"]) if current["token"] else None
    except (KeyError, TypeError, ValueError) as exc:
        raise SourceError("invalid_cursor") from exc
    page = await reader.children(folder, cursor)
    if len(page.items) > 100:
        raise SourceError("invalid_response")
    entries = []
    page_items: dict[str, RemoteItem] = {}
    for item in page.items:
        if item.scope != scope or item.parents != (folder,):
            raise SourceError("scope_mismatch")
        previous = page_items.get(item.item_id)
        if previous is not None:
            if previous != item:
                raise SourceError("version_changed")
            continue
        page_items[item.item_id] = item
        if item.item_id in excluded:
            continue
        entries.append(WalkItem(item, path))
        if item.kind == "folder" and recursive:
            if item.item_id in seen or len(seen) >= 10000 or len(path) >= 256:
                raise SourceError("resync_required")
            seen.add(item.item_id)
            queue.append({"path": [*path, item.item_id], "token": None})
    if page.next_cursor:
        if (
            page.next_cursor.scope != scope
            or page.next_cursor.operation != "children:" + folder
            or page.next_cursor == cursor
        ):
            raise SourceError("invalid_cursor")
        queue.insert(0, {"path": list(path), "token": page.next_cursor.token})
    if not queue:
        return WalkPage(tuple(entries), None, True, len(page.items))
    return WalkPage(
        tuple(entries),
        {"selection": selection, "identity": identity, "queue": queue, "seen": sorted(seen)},
        False,
        len(page.items),
    )

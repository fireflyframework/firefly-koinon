# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Metadata-only folder proofs, bounded per review rather than per remote corpus."""

from dataclasses import dataclass
from typing import Protocol

from koinon.integrations.content_sources.dtos import RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit


class FolderReader(Protocol):
    async def root(self) -> RemoteItem: ...
    async def get_item(self, item_id: str) -> RemoteItem: ...


@dataclass(frozen=True, slots=True)
class FolderNode:
    id: str
    parent: str | None
    version: str | None
    kind: str = "folder"


@dataclass(frozen=True, slots=True)
class AncestryProof:
    nodes: tuple[FolderNode, ...]
    paths: tuple[tuple[str, tuple[str, ...]], ...]

    def ancestors(self, root: str) -> tuple[str, ...]:
        return dict(self.paths)[root]

    def root_kind(self, root: str) -> str:
        return {node.id: node.kind for node in self.nodes}[root]


class FolderAncestry:
    def __init__(
        self,
        reader: FolderReader,
        scope: SourceScope,
        *,
        max_roots: int = 100,
        max_depth: int = 64,
        max_nodes: int = 512,
    ):
        self.reader, self.scope = reader, scope
        self.max_roots, self.max_depth, self.max_nodes = max_roots, max_depth, max_nodes

    async def capture(self, roots: tuple[str, ...]) -> AncestryProof:
        _no_remote_unit()
        roots = tuple(dict.fromkeys(roots))
        if len(roots) > self.max_roots:
            raise SourceError("size_exceeded")
        drive_root = await self.reader.root()
        if drive_root.scope != self.scope or drive_root.kind != "folder" or drive_root.parents:
            raise SourceError("access_denied")
        nodes: dict[str, FolderNode] = {
            drive_root.item_id: FolderNode(drive_root.item_id, None, drive_root.version)
        }
        paths: list[tuple[str, tuple[str, ...]]] = []
        for root in roots:
            path: list[str] = []
            seen: set[str] = set()
            identifier: str | None = root
            while identifier is not None:
                if identifier in seen:
                    raise SourceError("invalid_response")
                if len(path) >= self.max_depth:
                    raise SourceError("size_exceeded")
                seen.add(identifier)
                path.append(identifier)
                if identifier not in nodes:
                    if len(nodes) >= self.max_nodes:
                        raise SourceError("size_exceeded")
                    item = await self.reader.get_item(identifier)
                    if (
                        item.scope != self.scope or item.item_id != identifier
                        or item.kind not in {"file", "folder"}
                        or item.kind == "file" and identifier != root
                    ):
                        raise SourceError("access_denied")
                    if len(item.parents) > 1:
                        raise SourceError("invalid_response")
                    nodes[identifier] = FolderNode(
                        identifier, next(iter(item.parents), None), item.version, item.kind
                    )
                if nodes[identifier].kind != "folder" and identifier != root:
                    raise SourceError("access_denied")
                identifier = nodes[identifier].parent
            # An omitted/inaccessible parent is not proof that this folder is a drive root.
            if path[-1] != drive_root.item_id:
                raise SourceError("access_denied")
            paths.append((root, tuple(path[1:])))
        return AncestryProof(tuple(nodes[key] for key in sorted(nodes)), tuple(paths))


def overlaps(
    proof: AncestryProof, left: str, left_recursive: bool, right: str, right_recursive: bool
) -> bool:
    def contains(parent, recursive, child):
        ancestors = proof.ancestors(child)
        return proof.root_kind(parent) == "folder" and (
            recursive and parent in ancestors or bool(ancestors) and ancestors[0] == parent
        )

    return (
        left == right
        or contains(left, left_recursive, right)
        or contains(right, right_recursive, left)
    )

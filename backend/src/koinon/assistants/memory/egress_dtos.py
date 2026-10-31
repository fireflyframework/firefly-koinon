# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private persistence envelope; these bindings are never recipient conversation data."""

from pydantic import Field

from koinon.evidence.dtos import ConversationSnapshot, Frozen, Identifier, Revision


class MemoryEgressPin(Frozen):
    id: Identifier
    sha256: Revision


class MemoryEgressBinding(Frozen):
    run_id: Identifier
    generation_id: Identifier | None = None
    manifest_sha256: Revision | None = None
    results: tuple[MemoryEgressPin, ...] = Field(default=(), max_length=2000)


class MemoryConversationSnapshot(ConversationSnapshot):
    memory_bindings: tuple[MemoryEgressBinding, ...] = Field(default=(), max_length=200, repr=False)
    memory_transfer_consented: bool = False


def stored_snapshot(value) -> MemoryConversationSnapshot:
    return MemoryConversationSnapshot.model_validate(value)

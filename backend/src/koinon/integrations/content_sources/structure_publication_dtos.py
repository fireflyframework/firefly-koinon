# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private structural publication identities; none is a reader or writer grant."""

import json
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=64, strict=True)]


class StructureWrite(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    catalog_id: Identifier
    action: Literal["rename", "move"]
    value: str = Field(min_length=1, max_length=255, strict=True)

    @model_validator(mode="after")
    def bound_parent(self):
        if self.action == "move" and len(self.value) > 64:
            raise ValueError("parent identifier exceeds 64 characters")
        return self

    def command(self) -> dict:
        field = "name" if self.action == "rename" else "parent_id"
        return {"catalog_id": self.catalog_id, "action": self.action, "fields": {field: self.value}}


def encode_structure_writes(writes: tuple[StructureWrite, ...]) -> str:
    if not 1 <= len(writes) <= 100:
        raise ValueError("structural publication requires 1 to 100 writes")
    encoded = json.dumps([write.command() for write in writes], separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 262144:
        raise ValueError("structural publication exceeds its byte bound")
    return encoded


@dataclass(frozen=True, slots=True)
class StructurePublicationIdentity:
    proof_id: str
    effective_revision: str
    content_attempt_id: str


@dataclass(frozen=True, slots=True)
class ResolvedSourcePublication:
    """Immutable JSON strings retain closed database snapshots without mutable aliases."""

    content_attempt_id: str
    content_acknowledgement_sha256: str
    effective_revision: str
    structure_publication_id: str | None
    source_id: str
    asset_id: str
    generation: int
    mapping_revision: int
    native_receipt_json: str
    effective_vector_json: str
    original_members_json: str

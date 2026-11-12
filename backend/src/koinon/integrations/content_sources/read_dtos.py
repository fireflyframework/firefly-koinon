# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable local origins and credential-free reader choices."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from koinon.integrations.content_sources.reader_access import RemoteFolderReadTarget, RemoteReadTarget


@dataclass(frozen=True, slots=True)
class LocalSourcePin:
    asset_id: str
    domain: Literal["canon", "structured"]
    native_workspace_id: str
    native_source_id: str
    version_id: str
    extraction_id: str | None = None
    part_id: str | None = None


@dataclass(frozen=True, slots=True)
class LocalFolderSourcePin:
    folder_id: str
    publication_id: str
    observation_id: str
    canonical_revision: int


class ReaderSourceSelection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    provider: Literal["sharepoint", "onedrive", "google_drive"]
    external_tenant: str | None = Field(default=None, min_length=1, max_length=1024)
    connection_id: str = Field(min_length=1, max_length=64)


class ReaderSelectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    operation_id: UUID
    connections: list[ReaderSourceSelection] = Field(max_length=100)

    @model_validator(mode="after")
    def unique_accounts(self):
        validate_selections(tuple(self.connections))
        return self


class ReaderSelectionOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    revision: int
    connections: tuple[ReaderSourceSelection, ...]


class ReaderReadInput(BaseModel):
    """Missing choices use saved preferences; an empty list deliberately uses none."""

    model_config = ConfigDict(extra="forbid")
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def unique_reader_accounts(self):
        if self.reader_source_connections is not None:
            validate_selections(tuple(self.reader_source_connections))
        return self


class ReaderPageInput(ReaderReadInput):
    page: int = Field(default=1, ge=1, le=100000, strict=True)
    page_size: int = Field(default=25, ge=1, le=100, strict=True)


def validate_selections(selections: tuple[ReaderSourceSelection, ...]) -> None:
    if len(selections) > 100 or len({(s.provider, s.external_tenant) for s in selections}) != len(selections):
        raise ValueError("Choose at most one account for each provider and organization")


@dataclass(frozen=True, slots=True)
class ResolvedSourceOrigin:
    pin: LocalSourcePin
    attempt_id: str
    mapping_id: str
    mapping_revision: int
    object_id: str
    generation: int
    target: RemoteReadTarget
    config_fingerprint: str = ""
    policy_id: str = ""
    authority_sha256: str = ""


@dataclass(frozen=True, slots=True)
class ResolvedFolderSourceOrigin:
    pin: LocalFolderSourcePin
    mapping_id: str
    mapping_revision: int
    object_id: str
    generation: int
    target: RemoteFolderReadTarget
    config_fingerprint: str
    policy_id: str
    authority_sha256: str
    binding_revision: int
    ancestry: tuple


@dataclass(frozen=True, slots=True)
class ReaderSelectionSnapshot:
    connections: tuple[ReaderSourceSelection, ...]
    revision: int | None

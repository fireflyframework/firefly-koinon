# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pydantic import Field, field_validator, model_validator

from koinon.assistants.dtos import Input, KnowledgeScope


def one_line(value: str | None) -> str:
    if (
        value is None
        or not value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValueError("Choose a nonempty, one-line name")
    return value.strip()


class FolderCreate(Input):
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = Field(default=None, min_length=1, max_length=64)
    scope: KnowledgeScope | None = None
    memory_enabled: bool = Field(default=False, strict=True)

    @field_validator("name")
    @classmethod
    def name_is_one_line(cls, value: str) -> str:
        return one_line(value)


class FolderPatch(Input):
    expected_revision: int = Field(ge=1, strict=True)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: str | None = Field(default=None, min_length=1, max_length=64)
    memory_enabled: bool = Field(default=False, strict=True)

    @field_validator("name")
    @classmethod
    def name_is_one_line(cls, value: str | None) -> str:
        return one_line(value)

    @model_validator(mode="after")
    def requires_change(self):
        if not self.model_fields_set - {"expected_revision"}:
            raise ValueError("Choose a folder change")
        return self


class ThreadPatch(Input):
    expected_revision: int = Field(ge=1, strict=True)
    title: str | None = Field(default=None, min_length=1, max_length=160)
    folder_id: str | None = Field(default=None, min_length=1, max_length=64)
    archived: bool | None = Field(default=None, strict=True)

    @field_validator("title")
    @classmethod
    def title_is_one_line(cls, value: str | None) -> str:
        return one_line(value)

    @field_validator("archived")
    @classmethod
    def archived_cannot_be_null(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("Choose whether the conversation is archived")
        return value

    @model_validator(mode="after")
    def requires_change(self):
        if not self.model_fields_set - {"expected_revision"}:
            raise ValueError("Choose a conversation change")
        return self


class TitleRequest(Input):
    agent_id: str = Field(min_length=1, max_length=64)
    expected_revision: int = Field(ge=1, strict=True)

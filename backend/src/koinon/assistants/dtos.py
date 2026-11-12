# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from koinon.assistants.connections import ModelParameters
from koinon.integrations.content_sources.read_dtos import ReaderSourceSelection, validate_selections


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KnowledgeScope(Input):
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)
    project_id: str | None = Field(default=None, min_length=1, max_length=64)
    collection_id: str | None = Field(default=None, min_length=1, max_length=64)
    asset_ids: list[str] | None = Field(default=None, max_length=128)


class ProviderInput(Input):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    kind: Literal["ollama", "openai", "anthropic"] | None = None
    api: Literal["chat", "responses", "messages"] | None = None
    base_url: str | None = Field(default=None, max_length=2048)
    model_ids: list[str] | None = Field(default=None, max_length=100)
    secret: SecretStr | None = Field(default=None, max_length=16384)
    enabled: bool | None = None


class AgentInput(Input):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    provider_id: str | None = Field(default=None, min_length=1, max_length=64)
    model_id: str | None = Field(default=None, min_length=1, max_length=255)
    model_options: ModelParameters | None = None
    tools: (
        list[Literal["search_knowledge", "inspect_schema", "query_dataset", "propose_catalog_update"]] | None
    ) = None
    scope: KnowledgeScope | None = None
    instructions: str | None = Field(default=None, max_length=8000)
    enabled: bool | None = None


class ThreadInput(Input):
    folder_id: str | None = Field(default=None, min_length=1, max_length=64)
    title: str = Field(default="New conversation", min_length=1, max_length=160)
    scope: KnowledgeScope = Field(default_factory=KnowledgeScope)


class RunInput(Input):
    agent_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=32000)
    scope: KnowledgeScope = Field(default_factory=KnowledgeScope)
    client_request_id: str = Field(min_length=1, max_length=255)
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)
    attachment_ids: list[Annotated[str, Field(min_length=1, max_length=64)]] = Field(
        default_factory=list, max_length=10
    )

    @model_validator(mode="after")
    def unique_source_choices(self):
        if self.reader_source_connections is not None:
            validate_selections(tuple(self.reader_source_connections))
        return self

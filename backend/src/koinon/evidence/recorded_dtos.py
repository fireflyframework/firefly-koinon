# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained evidence context is a selector, never a caller-supplied source grant."""

from typing import Annotated, Literal

from pydantic import Field, field_validator

from koinon.evidence.dtos import Frozen, Identifier, Revision
from koinon.integrations.content_sources.read_dtos import ReaderSourceSelection, validate_selections


class RecordedRunContext(Frozen):
    kind: Literal["run"]
    run_id: Identifier
    message_id: Identifier


class RecordedMessageSelection(Frozen):
    message_ids: list[Identifier] = Field(min_length=1, max_length=200)

    @field_validator("message_ids")
    @classmethod
    def distinct_messages(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Choose distinct messages")
        return value


class RecordedConversationContext(RecordedMessageSelection):
    kind: Literal["conversation"]
    thread_id: Identifier
    expected_manifest_revision: Revision


class RecordedShareContext(RecordedMessageSelection):
    kind: Literal["share"]
    share_id: Identifier
    expected_revision: Revision
    reader_source_connections: list[ReaderSourceSelection] | None = Field(max_length=100)

    @field_validator("reader_source_connections")
    @classmethod
    def distinct_choices(cls, value):
        if value is not None:
            validate_selections(value)
        return value


class RecordedDocumentReadInput(Frozen):
    source_reference_id: Identifier
    context: Annotated[
        RecordedRunContext | RecordedConversationContext | RecordedShareContext,
        Field(discriminator="kind"),
    ]

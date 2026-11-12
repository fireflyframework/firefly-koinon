# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Closed structural commands cannot carry content or arbitrary catalog patches."""

import pytest
from pydantic import ValidationError


def test_structural_commands_only_encode_one_name_or_parent_change():
    from koinon.integrations.content_sources.structure_publication_dtos import StructureWrite

    rename = StructureWrite(catalog_id="source", action="rename", value="Renamed")
    move = StructureWrite(catalog_id="source", action="move", value="collection")
    assert rename.command() == {"catalog_id": "source", "action": "rename", "fields": {"name": "Renamed"}}
    assert move.command() == {"catalog_id": "source", "action": "move", "fields": {"parent_id": "collection"}}
    for invalid in (
        {"catalog_id": "source", "action": "rename", "value": ""},
        {"catalog_id": "source", "action": "move", "value": "x" * 65},
        {"catalog_id": "source", "action": "rename", "value": "x" * 256},
        {"catalog_id": "source", "action": "update", "value": "ready"},
        {"catalog_id": "source", "action": "rename", "value": "name", "metadata": {}},
    ):
        with pytest.raises(ValidationError):
            StructureWrite.model_validate(invalid)
    with pytest.raises(ValidationError):
        rename.value = "Changed after admission"


def test_structural_command_program_is_nonempty_and_bounded():
    from koinon.integrations.content_sources.structure_publication_dtos import (
        StructureWrite,
        encode_structure_writes,
    )

    write = StructureWrite(catalog_id="source", action="rename", value="Name")
    assert len(encode_structure_writes((write,) * 100)) <= 262144
    with pytest.raises(ValueError, match="1 to 100"):
        encode_structure_writes(())
    with pytest.raises(ValueError, match="1 to 100"):
        encode_structure_writes((write,) * 101)

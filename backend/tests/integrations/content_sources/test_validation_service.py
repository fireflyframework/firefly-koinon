# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Preparation capabilities and complete-manifest identity, without provider credentials."""

import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_validation_dtos import SourceMappingValidationInput


def selection(**changes):
    return SourceMappingValidationInput(
        operation_id=uuid4(),
        connection_id="connection",
        drive_id="drive",
        root_id="root",
        destination={"workspace_id": "workspace", "project_id": "project", "parent_id": "folder"},
        recursive=True,
        removal_policy="retire",
        **changes,
    )


def test_existing_mapping_requires_exact_revision():
    with pytest.raises(ValidationError):
        selection(mapping_id="mapping")
    with pytest.raises(ValidationError):
        selection(expected_revision=1)
    assert selection(mapping_id="mapping", expected_revision=2).expected_revision == 2


def test_selection_identity_excludes_operation_and_validation_control_fields():
    first, second = selection(), selection()
    assert first.selection().model_dump() == second.selection().model_dump()
    assert "operation_id" not in first.selection().model_dump()


def token_context():
    from koinon.integrations.content_sources.mapping_validation import ValidationTokens

    settings = SimpleNamespace(master_key=base64.urlsafe_b64encode(bytes(range(32))).decode())
    now = datetime.now(UTC)
    row = SimpleNamespace(
        id=uuid4(),
        tenant_id="tenant",
        owner="issuer|alice",
        session_hash="s" * 64,
        request_sha256="r" * 64,
        revision=3,
        expires_at=now + timedelta(hours=1),
    )
    return ValidationTokens(SourceCredentialVault(settings)), row, now


def test_continuation_cannot_be_used_for_page_or_other_session():
    tokens, row, now = token_context()
    value = tokens.issue(row, "continue")
    assert tokens.read(row, value, "continue", now)["revision"] == 3
    with pytest.raises(SourceError, match="invalid_cursor"):
        tokens.read(row, value, "items", now)
    row.session_hash = "other"
    with pytest.raises(SourceError, match="invalid_cursor"):
        tokens.read(row, value, "continue", now)


def test_cursor_absolute_expiry_and_tenant_binding():
    tokens, row, now = token_context()
    value = tokens.issue(row, "items", position=51)
    assert tokens.read(row, value, "items", now)["position"] == 51
    with pytest.raises(SourceError, match="invalid_cursor"):
        tokens.read(row, value, "items", row.expires_at)
    row.tenant_id = "foreign"
    with pytest.raises(SourceError, match="invalid_cursor"):
        tokens.read(row, value, "items", now)


def test_manifest_hash_ignores_page_boundaries_but_binds_action_destination_and_selection():
    from koinon.integrations.content_sources.mapping_validation import manifest_digest

    header = {
        "selection": selection().selection().model_dump(mode="json"),
        "root": {"id": "root"},
        "authority": "a" * 64,
        "checkpoint": {"operation": "changes", "token": "terminal"},
    }
    entries = [
        ("one", "a" * 64, ["Reports", "A.txt"], "create"),
        ("two", "b" * 64, ["Reports", "B.txt"], "create"),
    ]
    expected = manifest_digest(header, iter(entries))
    assert expected == manifest_digest(header, iter([*entries[:1], *entries[1:]]))
    assert expected != manifest_digest(header, iter([entries[0], (*entries[1][:3], "replace")]))
    assert expected != manifest_digest({**header, "authority": "changed"}, iter(entries))


def test_changed_fingerprint_counts_duplicates_without_masking_changes():
    from koinon.integrations.content_sources.mapping_validation import raw_budget

    assert raw_budget(99, 1, 100) == (100, False)
    assert raw_budget(100, 0, 100) == (100, False)
    assert raw_budget(100, 1, 100) == (101, True)
    with pytest.raises(SourceError):
        raw_budget(0, 101, 100000)


def test_effective_file_selection_changes_only_recursive_and_leaves_creation_immutable():
    from koinon.integrations.content_sources.mapping_validation import effective_selection

    original = selection().selection()
    effective = effective_selection(original, "file")
    assert not effective.recursive and original.recursive
    assert effective.hierarchy == original.hierarchy == "preserve"
    assert effective_selection(original, "folder") == original
    excluded = selection(excluded_ids=["other"]).selection()
    from koinon.jobs.errors import JobConflict

    with pytest.raises(JobConflict) as error:
        effective_selection(excluded, "file")
    assert error.value.code == "SOURCE_INVALID_SELECTION"


async def test_saved_eligibility_is_rejected_when_current_runtime_has_no_parser():
    from dataclasses import asdict

    from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
    from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
    from koinon.jobs.errors import JobConflict

    tokens, row, _ = token_context()
    service = object.__new__(SourceMappingValidations)
    service.vault = tokens.vault
    selected = selection(formats=[".futureformat"]).selection()
    remote = RemoteItem(
        SourceScope(Account("google_drive", "subject"), "drive"),
        "file",
        "file.futureformat",
        "file",
        "v1",
        7,
        "application/octet-stream",
        ("root",),
        True,
    )
    candidate = {
        "remote": asdict(remote),
        "filename": "file.futureformat",
        "export_mime": None,
        "reason": None,
        "parent": None,
    }
    entry = SimpleNamespace(item_id="file", candidate_ciphertext=service._encrypt(row, "entry", candidate))
    with pytest.raises(JobConflict) as error:
        await service._presentation(row, entry, selected, {})
    assert error.value.code == "SOURCE_VALIDATION_CHANGED"

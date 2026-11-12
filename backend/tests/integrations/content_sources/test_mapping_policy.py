# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviewed policy serialization preserves user intent without ambient defaults."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput


def policy(**overrides):
    return MappingReviewInput.model_validate(
        {
            "connection_id": "connection",
            "drive_id": "drive",
            "root_id": "root",
            "destination": {"workspace_id": "workspace", "project_id": "project", "parent_id": "folder"},
            "recursive": True,
            "removal_policy": "retire",
            **overrides,
        }
    )


def test_policy_preserves_explicit_selection_and_calendar():
    value = policy(
        mode="dataset",
        hierarchy="flatten",
        excluded_ids=["private-folder"],
        formats=[".csv"],
        schedule={"kind": "calendar", "timezone": "America/New_York", "time": "02:30", "weekdays": [1, 5]},
    )
    encoded = value.model_dump(mode="json")
    assert encoded["mode"] == "dataset"
    assert encoded["excluded_ids"] == ["private-folder"]
    assert encoded["schedule"] == {
        "kind": "calendar",
        "timezone": "America/New_York",
        "time": "02:30",
        "weekdays": [1, 5],
    }
    assert MappingReviewInput.model_validate(encoded) == value


@pytest.mark.parametrize(
    "change",
    [
        {"excluded_ids": ["same", "same"]},
        {"excluded_ids": ["bad\nidentifier"]},
        {"formats": ["*.csv"]},
        {"formats": [".CSV"]},
        {"formats": []},
        {"schedule": {"kind": "interval", "seconds": True}},
        {"schedule": {"kind": "interval", "seconds": 899}},
        {"schedule": {"kind": "calendar", "timezone": "Not/AZone", "time": "02:30"}},
        {"schedule": {"kind": "calendar", "timezone": "UTC", "time": "24:00"}},
        {"schedule": {"kind": "calendar", "timezone": "UTC", "time": "12:00", "weekdays": [1, 1]}},
    ],
)
def test_policy_rejects_ambiguous_or_unbounded_rules(change):
    with pytest.raises(ValidationError):
        policy(**change)


def test_reviewed_replacement_retains_exact_choices_and_rejects_ambiguous_ids():
    retained, removed = str(uuid4()), str(uuid4())
    resolution = {
        "object_id": "object",
        "remote_version": "remote-v2",
        "content_sha256": "a" * 64,
        "baseline_sha256": "b" * 64,
        "new_locator_set_sha256": "c" * 64,
        "replacements": [{"new_locator": "root", "previous_table_id": retained}],
        "removed_table_ids": [removed],
    }
    value = policy(mode="dataset", replacement_resolutions=[resolution])
    assert value.model_dump(mode="json")["replacement_resolutions"] == [resolution]
    for invalid in (
        {**resolution, "replacements": resolution["replacements"] * 2},
        {**resolution, "removed_table_ids": [retained]},
        {**resolution, "removed_table_ids": [removed, removed]},
        {**resolution, "replacements": [{"new_locator": "root", "previous_table_id": retained.upper()}]},
        {**resolution, "replacements": [{"new_locator": "é" * 1025, "previous_table_id": None}]},
        {**resolution, "unexpected": True},
    ):
        with pytest.raises(ValidationError):
            policy(mode="dataset", replacement_resolutions=[invalid])
    with pytest.raises(ValidationError):
        policy(mode="dataset", replacement_resolutions=[resolution, resolution])
    with pytest.raises(ValidationError):
        policy(mode="document", replacement_resolutions=[resolution])


def test_validation_capacity_cannot_exceed_installation_limits_or_underreserve_a_full_scan():
    from koinon.integrations.content_sources.settings import ContentSourceSettings

    settings = ContentSourceSettings()
    settings.synchronization_options()
    assert settings.sync_validation_max_active_per_tenant == 8
    for changed in (
        {"sync_validation_max_active_per_tenant": 9},
        {"sync_validation_max_active_per_owner": 3},
        {"sync_validation_max_active_per_tenant": 1, "sync_validation_max_active_per_owner": 2},
        {"sync_validation_max_records_per_tenant": 1001},
        {"sync_validation_max_records_per_tenant": 7},
        {"sync_validation_max_retained_bytes_per_tenant": 17179869185},
        {"sync_validation_max_retained_bytes_per_tenant": 100000 * 16384 + 8388607},
        {"sync_validation_max_active_per_owner": True},
    ):
        with pytest.raises(ValueError):
            ContentSourceSettings(**changed).synchronization_options()
    exact = ContentSourceSettings(sync_validation_max_retained_bytes_per_tenant=100000 * 16384 + 8388608)
    exact.synchronization_options()

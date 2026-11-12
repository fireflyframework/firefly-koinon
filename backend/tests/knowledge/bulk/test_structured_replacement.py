# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID, uuid4

import pytest
from flyquery.core.services.ingestion.reader import ProposedTable
from pyfly.kernel import ConflictException


def member(key):
    return dict(
        member_key=key,
        table_id=str(uuid4()),
        catalog_table_id=str(uuid4()),
        snapshot_id=str(uuid4()),
        source_file_id=str(uuid4()),
        local_revision="1",
        sha256="a" * 64,
    )


@pytest.mark.parametrize("changed", ["duplicate", "foreign_file", "missing", "oversized"])
def test_replacement_baseline_requires_a_complete_unique_bounded_original(changed):
    from pydantic import ValidationError
    from koinon.knowledge.bulk.structured_dtos import DatasetReplacementBaseline

    previous = member("root")
    body = dict(
        schema="koinon.dataset-replacement-baseline.v1", dataset_id=str(uuid4()),
        catalog_dataset_id="dataset", source_attempt_id="attempt", imported_version_id="attempt",
        catalog_file_version_id="version", policy_id="policy", local_revision="cpv1:" + "c" * 64,
        source_generation=1, policy_revision=1, sha256="a" * 64,
        native_file_id=previous["source_file_id"], members=[previous],
    )
    original = DatasetReplacementBaseline.model_validate(body)
    assert original.members[0].member_key == "root"
    if changed == "duplicate":
        body["members"] = [previous, previous]
    elif changed == "foreign_file":
        body["members"] = [{**previous, "source_file_id": str(uuid4())}]
    elif changed == "missing":
        body["members"] = []
    else:
        body["members"] = [{**member(str(i)), "source_file_id": previous["source_file_id"]} for i in range(17)]
    with pytest.raises(ValidationError):
        DatasetReplacementBaseline.model_validate(body)


def test_workbook_growth_and_reordering_preserve_complete_member_identity():
    from koinon.knowledge.bulk.structured_replacement import discover_members, plan_members

    before = discover_members(
        "xlsx",
        (
            ProposedTable("Sales", "Sales#section[1:10]", 2, 9),
            ProposedTable("Costs", "Costs#section[1:10]", 2, 9),
        ),
    )
    after = discover_members(
        "xlsx",
        (
            ProposedTable("Costs", "Costs#section[1:40]", 2, 39),
            ProposedTable("Sales", "Sales#section[1:100]", 2, 99),
        ),
    )
    baseline = tuple(member(value.locator) for value in before)
    operation = uuid4()
    result = plan_members(operation, baseline, after)
    assert [value.action for value in result] == ["retain", "retain"]
    for value, previous in zip(result, reversed(baseline), strict=True):
        assert str(value.table_id) == previous["table_id"]
        assert value.catalog_table_id == previous["catalog_table_id"]
        assert str(value.snapshot_id) != previous["snapshot_id"]
    assert plan_members(operation, baseline, after) == result


def test_rename_requires_exact_review_bijection_and_bound_bytes():
    from koinon.integrations.content_sources.mapping_dtos import ReplacementResolutionInput
    from koinon.knowledge.bulk.structured_replacement import discover_members, locator_digest, plan_members

    before = discover_members("json", (ProposedTable("old", "old", 2, 4),))
    after = discover_members("json", (ProposedTable("new", "new", 2, 5),))
    baseline = (member(before[0].locator),)
    operation = uuid4()
    with pytest.raises(ConflictException, match="review"):
        plan_members(operation, baseline, after)
    resolution = ReplacementResolutionInput(
        object_id="object",
        remote_version="v2",
        content_sha256="c" * 64,
        baseline_sha256="b" * 64,
        new_locator_set_sha256=locator_digest(after),
        replacements=[dict(new_locator=after[0].locator, previous_table_id=baseline[0]["table_id"])],
    )
    scope = dict(
        resolution=resolution,
        object_id="object",
        remote_version="v2",
        content_sha256="c" * 64,
        baseline_sha256="b" * 64,
    )
    result = plan_members(operation, baseline, after, **scope)
    assert len(result) == 1 and str(result[0].table_id) == baseline[0]["table_id"]
    assert result[0].member_key == after[0].locator
    for change in (
        dict(content_sha256="d" * 64),
        dict(baseline_sha256="d" * 64),
        dict(remote_version="v3"),
        dict(object_id="other"),
    ):
        with pytest.raises(ConflictException):
            plan_members(operation, baseline, after, **{**scope, **change})
    foreign = resolution.model_copy(
        update={
            "replacements": [
                resolution.replacements[0].model_copy(update={"previous_table_id": str(uuid4())})
            ]
        }
    )
    with pytest.raises(ConflictException):
        plan_members(operation, baseline, after, **{**scope, "resolution": foreign})


def test_multiple_sections_and_unreliable_history_require_review():
    from koinon.knowledge.bulk.structured_replacement import discover_members, plan_members

    discovered = discover_members(
        "xlsx",
        (
            ProposedTable("one", "Sheet#section[1:10]", 2, 9),
            ProposedTable("two", "Sheet#section[12:20]", 2, 8),
        ),
    )
    with pytest.raises(ConflictException, match="review"):
        plan_members(uuid4(), tuple(member(value.locator) for value in discovered), discovered)
    with pytest.raises(ConflictException, match="review"):
        plan_members(
            uuid4(), (member("ordinal:0"),), discover_members("csv", (ProposedTable("x", None, 2, 3),))
        )


def test_reviewed_split_can_replace_same_locator_with_a_new_identity():
    from koinon.integrations.content_sources.mapping_dtos import ReplacementResolutionInput
    from koinon.knowledge.bulk.structured_replacement import discover_members, locator_digest, plan_members

    before = discover_members("json", (ProposedTable("facts", "facts", 2, 4),))
    after = discover_members(
        "json",
        (
            ProposedTable("facts", "facts", 2, 5),
            ProposedTable("details", "details", 3, 5),
        ),
    )
    baseline = (member(before[0].locator),)
    resolution = ReplacementResolutionInput(
        object_id="object",
        remote_version="v2",
        content_sha256="c" * 64,
        baseline_sha256="b" * 64,
        new_locator_set_sha256=locator_digest(after),
        replacements=[dict(new_locator=value.locator, previous_table_id=None) for value in after],
        removed_table_ids=[baseline[0]["table_id"]],
    )
    result = plan_members(
        uuid4(),
        baseline,
        after,
        resolution=resolution,
        object_id="object",
        remote_version="v2",
        content_sha256="c" * 64,
        baseline_sha256="b" * 64,
    )
    assert [value.action for value in result] == ["add", "add", "remove"]
    assert result[0].member_key == result[2].member_key
    assert result[0].table_id != result[2].table_id
    assert result[2].snapshot_id == UUID(baseline[0]["snapshot_id"])

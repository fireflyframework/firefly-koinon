# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Whole-file member identity is structural and reviewed, never inferred from ordinal."""

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from uuid import UUID, uuid5

from flyquery.core.services.ingestion.reader import ProposedTable
from flyquery.core.services.ingestion.readers.excel_reader import ExcelReader
from pyfly.kernel import ConflictException

from koinon.integrations.content_sources.mapping_dtos import ReplacementResolutionInput
from koinon.knowledge.bulk.structured_dtos import (
    PARSER_FINGERPRINT as PARSER_FINGERPRINT,
)
from koinon.knowledge.bulk.structured_dtos import (
    ReplacementMemberPlan as ReplacementMemberPlan,
)


def _review():
    return ConflictException(
        "Dataset members require a fresh explicit review", code="SOURCE_MEMBER_REVIEW_REQUIRED"
    )


def _encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(frozen=True, slots=True)
class DiscoveredMember:
    locator: str
    ordinal: int
    name: str
    ambiguous: bool = False


def discover_members(file_format: str, proposed: tuple[ProposedTable, ...]) -> tuple[DiscoveredMember, ...]:
    if not 1 <= len(proposed) <= 16:
        raise _review()
    sheets = (
        [ExcelReader._parse_section_path(item.sheet_or_json_path or "") for item in proposed]
        if file_format in {"xlsx", "xls", "ods"}
        else []
    )
    counts = Counter(value[0] for value in sheets)
    result = []
    for ordinal, item in enumerate(proposed):
        ambiguous = False
        if sheets:
            sheet, header, start, _ = sheets[ordinal]
            if not sheet:
                raise _review()
            ambiguous = counts[sheet] > 1
            if ambiguous and (header is None or start is None):
                raise _review()
            path = [sheet, header, start] if ambiguous else [sheet]
            locator = "worksheet:" + _encoded(path)
        elif file_format in {"json", "jsonl", "ndjson"} and item.sheet_or_json_path is not None:
            locator = "json:" + _encoded([item.sheet_or_json_path])
        else:
            if len(proposed) != 1 or item.sheet_or_json_path is not None:
                raise _review()
            locator = "root"
        if len(locator.encode("utf-8")) > 2048:
            raise _review()
        result.append(DiscoveredMember(locator, ordinal, item.name, ambiguous))
    if len({value.locator for value in result}) != len(result):
        raise _review()
    return tuple(result)


def locator_digest(discovered: tuple[DiscoveredMember, ...]) -> str:
    return hashlib.sha256(
        _encoded(
            {
                "parser": PARSER_FINGERPRINT,
                "locators": sorted(value.locator for value in discovered),
            }
        ).encode()
    ).hexdigest()


def _reliable(key: str) -> bool:
    if key == "root":
        return True
    try:
        prefix, encoded = key.split(":", 1)
        decoded = json.loads(encoded)
        return (
            prefix in {"json", "worksheet"}
            and isinstance(decoded, list)
            and len(decoded) == 1
            and isinstance(decoded[0], str)
            and _encoded(decoded) == encoded
        )
    except (ValueError, TypeError):
        return False


def plan_members(
    operation_id: UUID,
    baseline: tuple[dict, ...],
    discovered: tuple[DiscoveredMember, ...],
    *,
    resolution: ReplacementResolutionInput | None = None,
    object_id: str | None = None,
    remote_version: str | None = None,
    content_sha256: str | None = None,
    baseline_sha256: str | None = None,
) -> tuple[ReplacementMemberPlan, ...]:
    if not 1 <= len(baseline) <= 16 or not 1 <= len(discovered) <= 16:
        raise _review()
    old = {value["member_key"]: value for value in baseline}
    previous = {value["table_id"]: value for value in baseline}
    fresh = {value.locator: value for value in discovered}
    if len(old) != len(baseline) or len(previous) != len(baseline) or len(fresh) != len(discovered):
        raise _review()
    if len({value["catalog_table_id"] for value in baseline}) != len(baseline):
        raise _review()
    if resolution is None:
        if (
            any(value.ambiguous for value in discovered)
            or not all(_reliable(key) for key in old)
            or set(old) - set(fresh)
            and set(fresh) - set(old)
        ):
            raise _review()
        retained = {key: old[key]["table_id"] if key in old else None for key in fresh}
        removed = [value["table_id"] for key, value in old.items() if key not in fresh]
    else:
        if (
            resolution.object_id,
            resolution.remote_version,
            resolution.content_sha256,
            resolution.baseline_sha256,
            resolution.new_locator_set_sha256,
        ) != (object_id, remote_version, content_sha256, baseline_sha256, locator_digest(discovered)):
            raise _review()
        retained = {value.new_locator: value.previous_table_id for value in resolution.replacements}
        removed = resolution.removed_table_ids
        identities = [value for value in retained.values() if value is not None] + removed
        if (
            set(retained) != set(fresh)
            or len(retained) != len(resolution.replacements)
            or set(identities) != set(previous)
            or len(set(identities)) != len(identities)
        ):
            raise _review()
    plans = []
    for item in discovered:
        prior = previous.get(retained[item.locator])
        plans.append(
            ReplacementMemberPlan(
                member_key=item.locator,
                action="retain" if prior else "add",
                table_id=UUID(prior["table_id"]) if prior else uuid5(operation_id, "table:" + item.locator),
                catalog_table_id=prior["catalog_table_id"]
                if prior
                else str(uuid5(operation_id, "catalog:" + item.locator)),
                snapshot_id=uuid5(operation_id, "snapshot:" + item.locator),
                ordinal=item.ordinal,
                name=item.name,
            )
        )
    for identifier in removed:
        prior = previous[identifier]
        plans.append(
            ReplacementMemberPlan(
                member_key=prior["member_key"],
                action="remove",
                table_id=UUID(identifier),
                catalog_table_id=prior["catalog_table_id"],
                snapshot_id=UUID(prior["snapshot_id"]),
            )
        )
    live = [value.member_key for value in plans if value.action != "remove"]
    retired = [value.member_key for value in plans if value.action == "remove"]
    if len(set(live)) != len(live) or len(set(retired)) != len(retired):
        raise _review()
    return tuple(plans)

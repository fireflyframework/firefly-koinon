# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest

from koinon.integrations.content_sources.mapping_dtos import (
    CalendarSchedule,
    IntervalSchedule,
    ManualSchedule,
)
from koinon.integrations.content_sources.sync_schedule import advance_occurrence, next_occurrence


def at(value):
    return datetime.fromisoformat(value).astimezone(UTC)


@pytest.mark.parametrize(
    ("after", "expected"),
    [
        ("2026-03-08T06:00:00+00:00", "2026-03-08T07:00:00+00:00"),
        ("2026-03-08T07:00:00+00:00", "2026-03-09T06:30:00+00:00"),
    ],
)
def test_gap_runs_first_valid_instant_then_next_date(after, expected):
    schedule = CalendarSchedule(kind="calendar", timezone="America/New_York", time="02:30")
    assert next_occurrence(schedule, at(after)) == at(expected)


def test_overlap_does_not_run_again_at_second_fold():
    schedule = CalendarSchedule(kind="calendar", timezone="America/New_York", time="01:30")
    first = next_occurrence(schedule, at("2026-11-01T04:00:00+00:00"))
    assert first == at("2026-11-01T05:30:00+00:00")
    assert next_occurrence(schedule, first) == at("2026-11-02T06:30:00+00:00")


def test_half_hour_gap_and_weekday_selection():
    schedule = CalendarSchedule(kind="calendar", timezone="Australia/Lord_Howe", time="02:15", weekdays=[7])
    assert next_occurrence(schedule, at("2026-10-03T00:00:00+00:00")) == at("2026-10-03T15:30:00+00:00")


def test_interval_catchup_preserves_utc_phase_and_coalesces_missed_runs():
    schedule = IntervalSchedule(kind="interval", seconds=900)
    previous = at("2026-03-08T06:07:00+00:00")
    assert advance_occurrence(schedule, previous, at("2026-03-09T08:10:00+00:00")) == at(
        "2026-03-09T08:22:00+00:00"
    )
    assert next_occurrence(schedule, previous) == at("2026-03-08T06:22:00+00:00")


def test_manual_schedule_has_no_automatic_occurrence():
    assert next_occurrence(ManualSchedule(), at("2026-11-10T12:00:00+00:00")) is None


def test_naive_clock_is_rejected_instead_of_using_server_timezone():
    with pytest.raises(ValueError, match="timezone"):
        next_occurrence(IntervalSchedule(kind="interval", seconds=900), datetime(2026, 11, 10))

# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import pytest

from koinon.communications.calendar import digest_window, next_run
from koinon.communications.dtos import DigestSchedule


def instant(value):
    return datetime.fromisoformat(value).astimezone(UTC)


def test_monthly_clips_short_months_and_retains_requested_day_for_next_month():
    schedule = DigestSchedule(local_time="09:00", day_of_month=31)
    february = next_run("monthly", schedule, "America/New_York", instant("2026-01-31T14:00:00Z"))
    assert february == instant("2026-02-28T14:00:00Z")
    march = next_run("monthly", schedule, "America/New_York", february)
    assert march == instant("2026-03-31T13:00:00Z")
    assert digest_window("monthly", schedule, "America/New_York", march) == (february, march)


def test_daily_spring_gap_advances_to_first_valid_minute_and_fold_sends_once():
    gap = DigestSchedule(local_time="02:30")
    assert next_run("daily", gap, "America/Los_Angeles", instant("2026-03-07T12:00:00Z")) == instant(
        "2026-03-08T10:00:00Z"
    )
    fold = DigestSchedule(local_time="01:30")
    first = next_run("daily", fold, "America/Los_Angeles", instant("2026-10-31T12:00:00Z"))
    assert first == instant("2026-11-01T08:30:00Z")
    assert next_run("daily", fold, "America/Los_Angeles", instant("2026-11-01T08:45:00Z")) == instant(
        "2026-11-02T09:30:00Z"
    )


def test_weekly_uses_local_weekday_and_real_calendar_window():
    schedule = DigestSchedule(local_time="09:00", weekday=0)
    due = next_run("weekly", schedule, "Europe/Madrid", instant("2026-03-28T12:00:00Z"))
    assert due == instant("2026-03-30T07:00:00Z")
    assert digest_window("weekly", schedule, "Europe/Madrid", due) == (instant("2026-03-23T08:00:00Z"), due)


def test_off_has_no_run_and_invalid_clock_zone_or_naive_time_are_rejected():
    assert next_run("off", DigestSchedule(), "UTC", datetime.now(UTC)) is None
    for values in (
        dict(local_time="24:00"),
        dict(local_time="9:30"),
        dict(weekday=7),
        dict(day_of_month=0),
        dict(day_of_month=True),
    ):
        with pytest.raises(ValueError):
            DigestSchedule(**values)
    with pytest.raises(ValueError):
        next_run("monthly", DigestSchedule(), "Invented/Zone", datetime.now(UTC))
    with pytest.raises(ValueError):
        next_run("weekly", DigestSchedule(), "UTC", datetime(2026, 10, 31))

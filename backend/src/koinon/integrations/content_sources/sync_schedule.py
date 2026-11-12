# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Deterministic UTC occurrences for reviewed wall-clock schedules."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from koinon.integrations.content_sources.mapping_dtos import (
    CalendarSchedule,
    IntervalSchedule,
    SourceSchedule,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Schedule clocks require a timezone")
    return value.astimezone(UTC)


def _first_valid(wall: datetime, zone: ZoneInfo) -> datetime:
    # Roundtripping rejects imaginary local times. Minute schedules advance to
    # the first valid minute, including half-hour transitions and skipped dates.
    for minutes in range(2881):
        candidate = wall + timedelta(minutes=minutes)
        valid = []
        for fold in (0, 1):
            instant = candidate.replace(tzinfo=zone, fold=fold).astimezone(UTC)
            if instant.astimezone(zone).replace(tzinfo=None) == candidate:
                valid.append(instant)
        if valid:
            return min(valid)
    raise ValueError("No valid local schedule occurrence within two days")


def next_occurrence(schedule: SourceSchedule, after: datetime) -> datetime | None:
    after = _utc(after)
    if isinstance(schedule, IntervalSchedule):
        return after + timedelta(seconds=schedule.seconds)
    if not isinstance(schedule, CalendarSchedule):
        return None
    zone = ZoneInfo(schedule.timezone)
    local_date = after.astimezone(zone).date()
    hour, minute = map(int, schedule.time.split(":"))
    for offset in range(15):
        day = local_date + timedelta(days=offset)
        if day.isoweekday() not in schedule.weekdays:
            continue
        instant = _first_valid(datetime.combine(day, time(hour, minute)), zone)
        if instant > after:
            return instant
    raise ValueError("No calendar occurrence within schedule bounds")


def advance_occurrence(schedule: SourceSchedule, scheduled: datetime, now: datetime) -> datetime | None:
    """Coalesce overdue execution into one run while retaining interval phase."""
    scheduled, now = _utc(scheduled), _utc(now)
    if isinstance(schedule, IntervalSchedule):
        elapsed = max(0, (now - scheduled).total_seconds())
        periods = int(elapsed // schedule.seconds) + 1
        return scheduled + timedelta(seconds=periods * schedule.seconds)
    return next_occurrence(schedule, now)

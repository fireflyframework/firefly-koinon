# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Calendar launches use profile time zones, never fixed-second monthly intervals."""

import calendar
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from koinon.communications.dtos import DigestSchedule


def _zone(name):
    try:
        return ZoneInfo(name)
    except (ValueError, TypeError, ZoneInfoNotFoundError):
        raise ValueError("Use an IANA time zone") from None


def _clock(value):
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("Use an aware schedule clock")
    return value.astimezone(UTC)


def _month(day, offset, requested):
    year, month = divmod(day.year * 12 + day.month - 1 + offset, 12)
    month += 1
    return date(year, month, min(requested, calendar.monthrange(year, month)[1]))


def _date(frequency, schedule, current):
    if frequency == "daily":
        return current
    if frequency == "weekly":
        return current + timedelta(days=schedule.weekday - current.weekday())
    if frequency == "monthly":
        return _month(current, 0, schedule.day_of_month)
    raise ValueError("Choose a supported digest cadence")


def _shift(day, frequency, schedule, direction):
    if frequency == "monthly":
        return _month(day, direction, schedule.day_of_month)
    return day + timedelta(days=direction * (7 if frequency == "weekly" else 1))


def _instant(day, schedule, zone):
    hour, minute = map(int, schedule.local_time.split(":"))
    local = datetime(day.year, day.month, day.day, hour, minute)
    # Choose the first valid minute in a gap and the earlier instant in a repeated hour.
    for offset in range(2881):
        candidate = local + timedelta(minutes=offset)
        values = []
        for fold in (0, 1):
            aware = candidate.replace(tzinfo=zone, fold=fold)
            utc = aware.astimezone(UTC)
            restored = utc.astimezone(zone)
            if restored.replace(tzinfo=None) == candidate and restored.fold == fold:
                values.append(utc)
        if values:
            return min(values)
    raise ValueError("No bounded valid local launch time")


def next_run(frequency, schedule: DigestSchedule, time_zone, after):
    after = _clock(after)
    zone = _zone(time_zone)
    if frequency == "off":
        return None
    schedule = DigestSchedule.model_validate(schedule)
    day = _date(frequency, schedule, after.astimezone(zone).date())
    for _ in range(3):
        candidate = _instant(day, schedule, zone)
        if candidate > after:
            return candidate
        day = _shift(day, frequency, schedule, 1)
    raise ValueError("No bounded next digest launch")


def latest_run(frequency, schedule: DigestSchedule, time_zone, at):
    at = _clock(at)
    zone = _zone(time_zone)
    schedule = DigestSchedule.model_validate(schedule)
    day = _date(frequency, schedule, at.astimezone(zone).date())
    for _ in range(3):
        candidate = _instant(day, schedule, zone)
        if candidate <= at:
            return candidate
        day = _shift(day, frequency, schedule, -1)
    raise ValueError("No bounded prior digest launch")


def digest_window(frequency, schedule: DigestSchedule, time_zone, due):
    due = _clock(due)
    previous = latest_run(frequency, schedule, time_zone, due - timedelta(microseconds=1))
    if previous >= due:
        raise ValueError("A digest window must advance")
    return previous, due

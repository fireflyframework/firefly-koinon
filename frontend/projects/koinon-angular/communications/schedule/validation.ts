// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { DigestSchedule } from '@fireflyframework/koinon-angular/communications';
export function validDigestSchedule(value: DigestSchedule) {
  return (
    /^(?:[01][0-9]|2[0-3]):[0-5][0-9]$/.test(value.local_time) &&
    Number.isInteger(value.weekday) &&
    value.weekday >= 0 &&
    value.weekday <= 6 &&
    Number.isInteger(value.day_of_month) &&
    value.day_of_month >= 1 &&
    value.day_of_month <= 31
  );
}

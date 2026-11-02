// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { Presentation } from '@fireflyframework/koinon-sdk';

export type HourCycle = 'h11' | 'h12' | 'h23' | 'h24';

export function devicePresentation(): Presentation {
  try {
    const current = new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).resolvedOptions();
    return {
      locale: new Intl.Locale(current.locale, {
        calendar: current.calendar,
        hourCycle: current.hourCycle,
      }).toString(),
      time_zone: current.timeZone,
      response_language: 'auto',
    };
  } catch {
    return { locale: 'en-US', time_zone: 'UTC', response_language: 'auto' };
  }
}

export function presentationLocale(
  region: string,
  calendar: string,
  hourCycle: HourCycle,
  originalLocale = region,
): string {
  const original = new Intl.Locale(originalLocale);
  const extensions = original.toString().slice(original.baseName.length);
  return new Intl.Locale(new Intl.Locale(region).baseName + extensions, {
    calendar,
    hourCycle,
  }).toString();
}

// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonI18n } from './i18n';
import { devicePresentation, presentationLocale } from './presentation-preferences';

it('uses the device calendar, hour cycle and timezone without changing answer language', () => {
  const system = new Intl.DateTimeFormat(undefined, { hour: 'numeric' }).resolvedOptions();
  const device = devicePresentation();
  const selected = new Intl.Locale(device.locale);
  expect(selected.calendar).toBe(system.calendar);
  expect(selected.hourCycle).toBe(system.hourCycle);
  expect(device.time_zone).toBe(system.timeZone);
  expect(device.response_language).toBe('auto');
});

it('keeps other locale extensions when changing calendar, region and time format', () => {
  const locale = presentationLocale('es-MX', 'gregory', 'h23', 'en-US-u-nu-latn');
  const value = new Intl.Locale(locale);
  expect(value.baseName).toBe('es-MX');
  expect(value.numberingSystem).toBe('latn');
  expect(value.calendar).toBe('gregory');
  expect(value.hourCycle).toBe('h23');
});

it('formats frozen answer dates in their calendar and respects daylight saving transitions', () => {
  const i18n = TestBed.inject(KoinonI18n);
  const saved = {
    locale: 'en-US-u-ca-buddhist-hc-h23',
    time_zone: 'America/New_York',
    response_language: 'auto',
  };
  expect(i18n.date('2026-03-08T06:30:00Z', saved, 'time')).toBe('01:30');
  expect(i18n.date('2026-03-08T07:30:00Z', saved, 'time')).toBe('03:30');
  expect(i18n.date('2026-03-08', saved)).toContain('2569');
  i18n.apply({ locale: 'es-ES', time_zone: 'Europe/Madrid', response_language: 'es' });
  expect(i18n.date('2026-03-08T07:30:00Z', saved, 'time')).toBe('03:30');
});

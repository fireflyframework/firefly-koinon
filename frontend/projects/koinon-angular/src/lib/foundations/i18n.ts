// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, Pipe, inject, signal, type PipeTransform } from '@angular/core';
import type { Presentation } from '@fireflyframework/koinon-sdk';
import { SPANISH } from './spanish';
const INITIAL: Presentation = { locale: 'en-US', time_zone: 'UTC', response_language: 'en' };
@Injectable({ providedIn: 'root' })
export class KoinonI18n {
  readonly preferences = signal<Presentation>(INITIAL);
  apply(value: Presentation) {
    this.preferences.set({ ...value });
  }
  text(key: string) {
    return this.preferences().locale.toLowerCase().startsWith('es') ? (SPANISH[key] ?? key) : key;
  }
  date(
    raw: string | undefined,
    presentation: Presentation = this.preferences(),
    mode: 'date' | 'time' | 'datetime' = 'date',
  ): string {
    if (!raw) return '';
    const calendar = /^\d{4}-\d{2}-\d{2}$/.test(raw);
    if (!calendar && !/(Z|[+-]\d{2}:?\d{2})$/i.test(raw)) return raw;
    const date = new Date(calendar ? raw + 'T12:00:00Z' : raw);
    if (Number.isNaN(date.getTime()) || (calendar && date.toISOString().slice(0, 10) !== raw))
      return raw;
    try {
      return new Intl.DateTimeFormat(presentation.locale, {
        ...(mode === 'time' ? {} : ({ year: 'numeric', month: 'short', day: 'numeric' } as const)),
        ...(mode === 'date' ? {} : ({ hour: 'numeric', minute: '2-digit' } as const)),
        timeZone: calendar ? 'UTC' : presentation.time_zone,
      }).format(date);
    } catch {
      return raw;
    }
  }
  value(raw: unknown, dataType?: string, presentation: Presentation = this.preferences()): string {
    if (raw === null || raw === undefined) return '—';
    if (typeof raw === 'object') return JSON.stringify(raw);
    if (dataType && /^(DATE|TIMESTAMP|DATETIME)/i.test(dataType))
      return this.date(String(raw), presentation);
    if (
      typeof raw !== 'number' &&
      !(
        typeof raw === 'string' &&
        dataType &&
        /^(DECIMAL|NUMERIC|NUMBER|INTEGER|BIGINT|SMALLINT|INT\b|FLOAT|DOUBLE|REAL)/i.test(dataType)
      )
    )
      return String(raw);
    const value = String(raw),
      match = /^([+-]?)(\d+)(?:\.(\d+))?([eE][+-]?\d+)?$/.exec(value);
    if (!match) return value;
    try {
      const parts = new Intl.NumberFormat(presentation.locale).formatToParts(1.1),
        decimal = parts.find((part) => part.type === 'decimal')?.value ?? '.';
      // BigInt preserves arbitrary precision. Fraction and exponent remain the original decimal digits.
      const integer = match[4]
        ? match[2]
        : new Intl.NumberFormat(presentation.locale, { maximumFractionDigits: 0 }).format(
            BigInt(match[2]),
          );
      return (
        match[1] + integer + (match[3] === undefined ? '' : decimal + match[3]) + (match[4] ?? '')
      );
    } catch {
      return value;
    }
  }
}
@Pipe({ name: 'ffkText', pure: false })
export class KoinonTextPipe implements PipeTransform {
  private readonly i18n = inject(KoinonI18n);
  transform(key: string | null | undefined) {
    return this.i18n.text(key ?? '');
  }
}
@Pipe({ name: 'ffkDate', pure: false })
export class KoinonDatePipe implements PipeTransform {
  private readonly i18n = inject(KoinonI18n);
  transform(
    raw: string | null | undefined,
    presentation?: Presentation,
    mode: 'date' | 'time' | 'datetime' = 'date',
  ) {
    return this.i18n.date(raw ?? undefined, presentation, mode);
  }
}
@Pipe({ name: 'ffkValue', pure: false })
export class KoinonValuePipe implements PipeTransform {
  private readonly i18n = inject(KoinonI18n);
  transform(raw: unknown, dataType?: string, presentation?: Presentation) {
    return this.i18n.value(raw, dataType, presentation);
  }
}

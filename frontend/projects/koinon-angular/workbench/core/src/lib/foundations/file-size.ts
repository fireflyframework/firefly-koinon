// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
const units = ['KB', 'MB', 'GB', 'TB', 'PB', 'EB'] as const;

/** Decimal display units; transport and integrity checks retain exact byte counts. */
export function formatFileSize(bytes: number | null | undefined, locale: string): string {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return '—';
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  if (bytes === 0) return `${number.format(0)} KB`;
  if (bytes < 1000) return `< ${number.format(1)} KB`;
  let value = bytes / 1000;
  let unit = 0;
  while (Math.round(value * 10) / 10 >= 1000 && unit < units.length - 1) {
    value /= 1000;
    unit++;
  }
  return `${number.format(value)} ${units[unit]}`;
}

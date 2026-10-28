// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
function position(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value >= 0;
}
export function coordinateNumber(index: number | null): string | null {
  return position(index) ? (BigInt(index) + 1n).toString() : null;
}
export function sheetColumn(index: number | null): string | null {
  if (!position(index)) return null;
  let value = BigInt(index) + 1n;
  let result = '';
  while (value > 0n) {
    value -= 1n;
    result = String.fromCharCode(65 + Number(value % 26n)) + result;
    value /= 26n;
  }
  return result;
}
export function sheetCell(row: number, column: number): string | null {
  const letters = sheetColumn(column),
    number = coordinateNumber(row);
  return letters && number ? letters + number : null;
}
export function coordinateRange(start: number, count: number, stride = 1): string | null {
  if (!position(start) || !position(count) || !position(stride) || count < 1 || stride < 1)
    return null;
  const first = BigInt(start) + 1n;
  const last = first + (BigInt(count) - 1n) * BigInt(stride);
  return count === 1 ? first.toString() : `${first}–${last}`;
}
export function jsonPointer(parts: readonly (string | number)[]): string {
  return parts.length
    ? '/' + parts.map((part) => String(part).replace(/~/g, '~0').replace(/\//g, '~1')).join('/')
    : '';
}
export function coordinateFormat(
  format: string | null | undefined,
  variant: string | null | undefined,
): string {
  if (!format) return 'Format not recorded';
  if (format.toLowerCase() === 'excel') {
    if (variant?.toLowerCase() === 'ods') return 'OpenDocument spreadsheet';
    return ['xlsx', 'xls'].includes(variant?.toLowerCase() ?? '')
      ? 'Excel workbook'
      : 'Spreadsheet';
  }
  const names: Record<string, string> = {
    csv: 'CSV',
    tsv: 'Tab-separated file',
    json: 'JSON',
    jsonl: 'JSON Lines',
    parquet: 'Parquet',
    arrow: 'Apache Arrow',
    feather: 'Apache Arrow',
    orc: 'Apache ORC',
    avro: 'Apache Avro',
  };
  return names[format.toLowerCase()] ?? 'Source file';
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  coordinateNumber,
  coordinateRange,
  sheetColumn,
  sheetCell,
  jsonPointer,
  coordinateFormat,
} from './coordinate-labels';
it('formats spreadsheet positions without confusing zero-based records with A1 labels', () => {
  expect(sheetColumn(0)).toBe('A');
  expect(sheetColumn(25)).toBe('Z');
  expect(sheetColumn(26)).toBe('AA');
  expect(sheetColumn(16383)).toBe('XFD');
  expect(sheetCell(3, 6)).toBe('G4');
  expect(coordinateNumber(0)).toBe('1');
  expect(coordinateNumber(Number.MAX_SAFE_INTEGER)).toBe('9007199254740992');
  expect(sheetColumn(-1)).toBeNull();
  expect(sheetCell(0.5, 3)).toBeNull();
});
it('keeps compressed source strides explicit without inventing intermediate rows', () => {
  expect(coordinateRange(3, 1)).toBe('4');
  expect(coordinateRange(3, 3)).toBe('4–6');
  expect(coordinateRange(3, 3, 2)).toBe('4–8');
  expect(coordinateRange(Number.MAX_SAFE_INTEGER, 2)).toBe('9007199254740992–9007199254740993');
  expect(coordinateRange(0, 0)).toBeNull();
  expect(coordinateRange(0, 2, 0)).toBeNull();
});
it('escapes actual JSON keys and leaves original array positions zero-based', () => {
  expect(jsonPointer(['a/b', 0, '~value'])).toBe('/a~1b/0/~0value');
  expect(jsonPointer([])).toBe('');
  expect(jsonPointer(['0', ''])).toBe('/0/');
});
it('names observed formats and does not infer Excel for an unknown format', () => {
  expect(coordinateFormat('excel', 'xlsx')).toBe('Excel workbook');
  expect(coordinateFormat('excel', 'ods')).toBe('OpenDocument spreadsheet');
  expect(coordinateFormat('jsonl', 'jsonl_record')).toBe('JSON Lines');
  expect(coordinateFormat('arrow', 'arrow_ipc_stream')).toBe('Apache Arrow');
  expect(coordinateFormat('future', 'custom')).toBe('Source file');
  expect(coordinateFormat('excel', 'unknown')).toBe('Spreadsheet');
  expect(coordinateFormat(null, null)).toBe('Format not recorded');
});
it('includes Spanish labels for the coordinate column view', async () => {
  const { LINEAGE_SPANISH } = await import('../../../../src/lib/foundations/lineage-spanish');
  expect(LINEAGE_SPANISH['Columns']).toBe('Columnas');
});

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import { fileType } from './file-type-icon';
it('identifies original Office, PDF and compressed CSV files without treating analysis mode as a format', () => {
  expect(
    ['file.pdf', 'file.docx', 'file.xlsx', 'file.pptx', 'file.csv.gz', 'unknown'].map(
      (name) => fileType(name).mark,
    ),
  ).toEqual(['PDF', 'W', 'X', 'P', 'CSV', '']);
  expect(fileType('Friendly name', 'xlsx').label).toBe('Spreadsheet');
  expect(fileType('Friendly name', 'dataset').mark).toBe('');
  expect(fileType('notes.odt').label).toBe('OpenDocument file');
});

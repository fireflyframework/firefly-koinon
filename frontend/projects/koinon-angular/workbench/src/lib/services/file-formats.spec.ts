// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import { fileFormatGroups } from '../../../core/src/lib/atoms/file-formats';

describe('server-provided file format presentation', () => {
  it('names common Office formats without inventing legacy PowerPoint support', () => {
    const groups = fileFormatGroups(['.docx', '.xlsx', '.csv', '.pptx', '.pdf', '.txt']);
    expect(groups.map((group) => group.label)).toEqual([
      'Word',
      'Excel',
      'PowerPoint',
      'PDF',
      'Text',
      'Datasets',
    ]);
    expect(groups.find((group) => group.label === 'PowerPoint')?.extensions).toEqual(['.pptx']);
    expect(groups.flatMap((group) => group.extensions)).not.toContain('.ppt');
  });
  it('keeps compressed suffixes in details and preserves unknown server formats', () => {
    const groups = fileFormatGroups([
      '.csv',
      '.csv.gz',
      '.csv.zip',
      '.xlsx',
      '.xlsx.gz',
      '.custom',
    ]);
    expect(groups.find((group) => group.label === 'Excel')?.extensions).toEqual([
      '.xlsx',
      '.xlsx.gz',
    ]);
    expect(groups.find((group) => group.label === 'Datasets')?.extensions).toEqual([
      '.csv',
      '.csv.gz',
      '.csv.zip',
    ]);
    expect(groups.find((group) => group.label === 'Other formats')?.extensions).toEqual([
      '.custom',
    ]);
    expect(groups.map((group) => group.summary).join(' ')).not.toContain('.gz');
  });
  it('never implies a format that the server did not advertise', () => {
    expect(fileFormatGroups(['.txt']).map((group) => group.label)).toEqual(['Text']);
    expect(fileFormatGroups([])).toEqual([]);
    expect(
      fileFormatGroups(['.PPT', '.ppt']).find((group) => group.label === 'PowerPoint')?.extensions,
    ).toEqual(['.ppt']);
  });
});

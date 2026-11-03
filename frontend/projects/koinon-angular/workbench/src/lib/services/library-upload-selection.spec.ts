// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import type { FileBatchCapabilities } from '@fireflyframework/koinon-sdk';
import { uploadModes, preferredUploadMode, transferProgress } from './library-upload-selection';
const caps: FileBatchCapabilities = {
  configured: true,
  modes: ['document', 'dataset'],
  max_files: 100,
  max_file_bytes: 134217728,
  max_batch_bytes: 536870912,
  max_active_batches_per_subject: 3,
  formats: [
    { mode: 'document', extensions: ['.pdf', '.docx', '.pptx', '.xlsx', '.csv'], available: true },
    { mode: 'dataset', extensions: ['.xlsx', '.csv', '.csv.gz'], available: true },
    { mode: 'document', extensions: ['.rtf'], available: false },
  ],
};
describe('file-specific upload choices', () => {
  it('uses document parsing for Office prose and datasets for admitted spreadsheets without inventing support', () => {
    expect(
      ['Review.DOCX', 'slides.pptx', 'report.pdf', 'totals.xlsx', 'data.csv', 'data.csv.gz'].map(
        (name) => preferredUploadMode(name, caps),
      ),
    ).toEqual(['document', 'document', 'document', 'dataset', 'dataset', 'dataset']);
    expect(preferredUploadMode('older.ppt', caps)).toBeNull();
    expect(preferredUploadMode('report.rtf', caps)).toBeNull();
    expect(preferredUploadMode('totals.xlsx', { ...caps, modes: ['document'] })).toBe('document');
    expect(preferredUploadMode('totals.xlsx', { ...caps, formats: [] })).toBeNull();
  });
  it('keeps dual-use JSON and HTML in read/search by default', () => {
    const dual = {
      ...caps,
      formats: ['document', 'dataset'].map((mode) => ({
        mode: mode as 'document' | 'dataset',
        extensions: ['.json', '.html'],
        available: true,
      })),
    };
    expect(preferredUploadMode('data.json', dual)).toBe('document');
    expect(preferredUploadMode('page.html', dual)).toBe('document');
  });
  it('offers a text-reading override only when that file has both installed parser choices', () => {
    expect(uploadModes('totals.xlsx', caps)).toEqual(['document', 'dataset']);
    expect(uploadModes('slides.pptx', caps)).toEqual(['document']);
  });
  it('counts only acknowledged original bytes and keeps processing separate', () => {
    const items = [
      { size_bytes: 10, status: 'staged' },
      { size_bytes: 30, status: 'awaiting_upload' },
    ];
    expect(transferProgress(items)).toEqual({ received: 10, total: 40, percent: 25 });
    expect(transferProgress([{ size_bytes: 10, status: 'queued' }])).toEqual({
      received: 10,
      total: 10,
      percent: 100,
    });
    expect(transferProgress([])).toEqual({ received: 0, total: 0, percent: 0 });
  });
});

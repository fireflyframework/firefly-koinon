// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { expect, it } from 'vitest';
import { formatFileSize } from './file-size';

it('uses readable decimal units for small originals, large files and complete batches', () => {
  expect([0, 35, 999, 1000, 1500, 999950, 134217728, 536870912, 2500000000, 3000000000000]
    .map((size) => formatFileSize(size, 'en-US')))
    .toEqual(['0 KB', '< 1 KB', '< 1 KB', '1 KB', '1.5 KB', '1 MB', '134.2 MB', '536.9 MB', '2.5 GB', '3 TB']);
});

it('respects regional decimals without turning unknown sizes into zero', () => {
  expect(formatFileSize(1500000, 'es-ES')).toBe('1,5 MB');
  for (const size of [null, undefined, -1, NaN, Infinity])
    expect(formatFileSize(size, 'en-US')).toBe('—');
});

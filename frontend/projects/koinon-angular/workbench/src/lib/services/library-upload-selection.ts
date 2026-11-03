// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { FileBatchCapabilities } from '@fireflyframework/koinon-sdk';
export type UploadMode = 'document' | 'dataset';
export function uploadModes(
  filename: string,
  capabilities: FileBatchCapabilities | null | undefined,
): UploadMode[] {
  if (!capabilities) return [];
  return capabilities.modes.filter((mode) =>
    capabilities.formats?.some(
      (format) =>
        format.mode === mode &&
        format.available &&
        format.extensions.some((extension) =>
          filename.toLowerCase().endsWith(extension.toLowerCase()),
        ),
    ),
  );
}
export function preferredUploadMode(
  filename: string,
  capabilities: FileBatchCapabilities | null | undefined,
): UploadMode | null {
  const modes = uploadModes(filename, capabilities);
  const original = filename.toLowerCase().replace(/\.(gz|bz2|zip)$/, '');
  const tabular = /\.(xlsx?|ods|csv|tsv|parquet|orc|arrow|ipc|feather|avro)$/.test(original);
  return tabular && modes.includes('dataset')
    ? 'dataset'
    : modes.includes('document')
      ? 'document'
      : (modes[0] ?? null);
}
export function transferProgress(
  items: readonly { size_bytes: number; status: string; job_id?: string | null }[],
) {
  const total = items.reduce((sum, item) => sum + item.size_bytes, 0);
  const received = items
    .filter(
      (item) => !!item.job_id || ['staged', 'queued', 'running', 'succeeded'].includes(item.status),
    )
    .reduce((sum, item) => sum + item.size_bytes, 0);
  return { received, total, percent: total ? Math.floor((received / total) * 100) : 0 };
}

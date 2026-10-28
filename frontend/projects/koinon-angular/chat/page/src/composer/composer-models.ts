// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export interface ComposerAgent {
  id: string;
  name: string;
  available: boolean;
  note?: string;
}
export interface ComposerAttachment {
  id: string;
  name: string;
  size: number;
  mediaType: string;
  state: 'selected' | 'uploading' | 'processing' | 'ready' | 'failed';
  previewUrl?: string;
  progress?: number;
  detail?: string;
  removeDisabled?: boolean;
}

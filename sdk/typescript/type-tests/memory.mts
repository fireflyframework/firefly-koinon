// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { FolderPatch, MemoryReceipt, OrganizationChatSettingsInput } from '../src/index.js';

const folder: FolderPatch = { expected_revision: 1, memory_enabled: false };
const organization: OrganizationChatSettingsInput = { expected_revision: 1, default_agent_id: null, memory: { allow_project_memory: false } };
// @ts-expect-error Explicit null must not reset a saved policy.
const invalid: OrganizationChatSettingsInput = { expected_revision: 1, default_agent_id: null, memory: null };
export function sources(receipt: MemoryReceipt): readonly string[] {
  return (receipt.turns ?? []).map((turn) => turn.thread_id);
}
void folder; void organization; void invalid;

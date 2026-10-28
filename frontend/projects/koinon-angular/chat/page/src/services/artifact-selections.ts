// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export type ExportSelection =
  | { kind: 'conversation'; thread_id: string; message_ids: string[] }
  | { kind: 'query_result'; dataset_id: string; query_id: string };
export interface ConversationSelection {
  thread_id: string;
  message_ids: string[];
}

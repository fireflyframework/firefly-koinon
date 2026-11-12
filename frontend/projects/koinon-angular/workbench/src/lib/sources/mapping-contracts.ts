// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export interface Destination {
  workspace_id: string;
  project_id: string;
  parent_id: string;
}
export interface DestinationPresentation {
  segments: { id: string; kind: string; name: string }[];
}
export type SourceSchedule =
  | { kind: 'manual' }
  | { kind: 'interval'; seconds: number }
  | { kind: 'calendar'; timezone: string; time: string; weekdays: number[] };
export interface MappingPolicy {
  connection_id: string;
  drive_id: string;
  root_id: string;
  destination: Destination;
  recursive: boolean;
  removal_policy: 'retire' | 'pause_for_review';
  schema_version: 1;
  mode: 'document' | 'dataset';
  hierarchy: 'preserve' | 'flatten';
  excluded_ids: string[];
  formats: string[];
  schedule: SourceSchedule;
}
export interface MappingPresentation {
  source_root: { name: string; relative_path: string[] } | null;
  destination: DestinationPresentation | null;
  unavailable_reason: 'access_denied' | 'reconnect_required' | 'unavailable' | null;
}
export interface MappingSummary {
  id: string;
  status: 'reviewed' | 'active' | 'paused' | 'reconnect_required' | 'retired';
  connection_id: string;
  policy_revision: number | null;
  latest_review_revision: number;
  control_revision: number | null;
  next_run_at: string | null;
  presentation: MappingPresentation;
}
export interface SourceMapping extends MappingSummary {
  revision: number;
  policy: MappingPolicy;
  can_pause: boolean;
  can_resume: boolean;
  can_retire: boolean;
  can_sync: boolean;
}
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
}
export interface PolicyReceipt {
  operation_id: string;
  receipt_id: string;
  action: 'review' | 'apply';
  mapping_id: string;
  policy_id: string;
  expected_policy_revision: number | null;
  result_policy_revision: number;
  review_digest: string;
  review_expires_at: string;
  disposition: 'reviewed' | 'accepted';
}
export interface PreviewItem {
  item_id: string;
  name: string;
  kind: string;
  version: string | null;
  filename: string;
  reason: string | null;
  ancestry: string[];
  relative_path: string[];
  size_bytes: number | null;
  action: 'create' | 'replace' | 'move' | 'skip' | 'conflict' | 'retire';
  destination_relative_path: string[];
  collision: 'none' | 'source_name' | 'destination_name' | 'local_edit';
}
export interface ReviewPage extends CursorPage<PreviewItem> {
  review_id: string;
  validation_id?: string | null;
  root_kind?: 'file' | 'folder';
  policy_revision: number;
  review_digest: string;
  expires_at: string;
  enumeration_complete: boolean;
  total: number | null;
  observed_count: number | null;
  known_bytes: number | null;
  unknown_size_count: number | null;
  can_apply: boolean;
  destination: DestinationPresentation;
}
export interface ControlReceipt {
  operation_id: string;
  receipt_id: string;
  action: 'sync' | 'pause' | 'resume' | 'cancel' | 'retry' | 'retire';
  control_revision: number;
  run_id: string | null;
  disposition: 'queued' | 'paused' | 'active' | 'stopping' | 'reconciling' | 'retired';
}

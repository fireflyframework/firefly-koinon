// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {
  HealthComponentId,
  HealthReason,
  HealthRemediation,
  SystemComponentVersion,
  SystemLimit,
} from '@fireflyframework/koinon-sdk/platform-health';
export const HEALTH_COMPONENTS: Record<HealthComponentId, string> = {
  'database-primary': 'Catalog database',
  'database-documents': 'Document database',
  'database-documents-control': 'Document database access policy',
  'database-structured': 'Dataset database',
  'database-structured-control': 'Dataset database access policy',
  'storage-documents': 'Document file storage',
  'storage-structured': 'Dataset file storage',
  'indexes-documents': 'Document search indexes',
  'indexes-structured': 'Dataset search indexes',
  'ingestion-documents': 'Document ingestion',
  'ingestion-structured': 'Dataset ingestion',
  'model-configuration': 'Knowledge model configuration',
  communications: 'Email communications',
  workers: 'Background workers',
};
export const HEALTH_REASONS: Record<HealthReason, string> = {
  DATABASE_OK: 'The database responded to a bounded connectivity check.',
  DATABASE_UNAVAILABLE: 'The database could not complete its connectivity check.',
  RUNTIME_ROLE_UNVERIFIED: 'The runtime database access policy has not been verified.',
  RUNTIME_ROLE_UNSAFE: 'The runtime database role does not meet the required access policy.',
  MODULE_DISABLED: 'This knowledge service is disabled in configuration.',
  STORAGE_NOT_PROBED:
    'File storage is configured. This report does not test reading or writing files.',
  INDEXES_VERIFIED: 'The returned search index checks passed.',
  INDEXES_INCOMPLETE: 'Some checked search indexes need attention.',
  INDEXES_NOT_PROBED: 'Search index readiness has not been observed.',
  NO_INDEXES: 'No search indexes were found in the checked scope.',
  INGESTION_STATE_OBSERVED: 'The report contains a bounded observation of processing records.',
  INGESTION_FAILURES: 'Some observed processing records contain failures.',
  MODEL_CONFIGURATION_PRESENT:
    'Model assignments are configured. Generation and connectivity have not been tested here.',
  MODEL_CONFIGURATION_INCOMPLETE: 'Required knowledge model assignments are missing or incomplete.',
  PROVIDER_NOT_PROBED: 'The provider has not been tested by this report.',
  COMMUNICATIONS_DISABLED: 'Email communications are disabled in configuration.',
  COMMUNICATIONS_CONFIGURED:
    'Email communications are configured. Delivery has not been tested here.',
  COMMUNICATIONS_INCOMPLETE: 'Email communications need additional configuration.',
  WORKER_LIVENESS_UNKNOWN:
    'No current worker heartbeat is available. Processing configuration does not confirm a running worker.',
  OBSERVATION_UNAVAILABLE: 'A current observation is unavailable.',
  OBSERVATION_BOUNDED:
    'This observation covers a limited sample. It does not describe every resource.',
  OBSERVATION_STALE:
    'This observation has expired. Refresh to request the latest available checks.',
};
export const HEALTH_REMEDIATIONS: Record<HealthRemediation, string> = {
  none: 'No action is suggested by this check.',
  retry_read: 'Refresh observations to request the latest available checks.',
  review_configuration:
    'Review the affected service configuration with your deployment administrator.',
  review_indexes:
    'Review search index assignments and indexing activity for the affected knowledge spaces.',
  review_ingestion:
    'Review processing activity and the source files associated with failed records.',
  review_communications:
    'Review the email provider and communications policy. This report does not send a test email.',
  review_worker:
    'Ask your deployment administrator to check worker execution and observation collection.',
};
export const SYSTEM_COMPONENTS: Record<SystemComponentVersion['id'], string> = {
  backend: 'koinon application',
  documents: 'Document knowledge',
  structured: 'Structured knowledge',
  storage: 'File storage',
  'python-sdk': 'Python SDK',
  framework: 'pyfly framework',
};
export const SYSTEM_LIMITS: Record<SystemLimit['id'], string> = {
  api_capacity: 'API operation capacity',
  worker_capacity: 'Worker operation capacity',
  worker_concurrency: 'Worker concurrency',
  max_index_workspaces: 'Knowledge spaces per index check',
  mcp_max_concurrency: 'MCP request concurrency',
  mcp_max_request_bytes: 'MCP request limit',
  mcp_max_response_bytes: 'MCP response limit',
  ingestion_raw_max_bytes: 'Source file size limit',
  ingestion_scratch_max_bytes: 'Processing scratch space limit',
  ingestion_child_rss_max_bytes: 'Document process memory limit',
};

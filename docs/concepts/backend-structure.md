# Backend structure

The application package is `koinon`, installed from `backend/src/koinon`. Start the API with `koinon.main:app` and the independent conversation worker with `python -m koinon.assistants.worker`.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `app.py` | Compose the native pyfly application context, security and API routes |
| `api/controllers` | Context, catalog, membership, audit and job HTTP endpoints |
| `catalog` | Knowledge hierarchy, persisted access grants and audit records |
| `knowledge` | Authorized document and dataset operations and domain bindings |
| `assistants` | Model configuration, agent scope, conversations, evidence and durable generation |
| `organization_chat` | One organization-wide chat default, scoped reads and revision-checked operator changes |
| `storage` | Private attachment ports and deployment profiles; shared cloud transport lives in the independent `koinon_storage` package |
| `profiles` | User preferences, avatars and author summaries |
| `tokens` | Scoped personal API credentials, expiration and revocation |
| `jobs` | Durable ingestion jobs, leases and authorized job management |
| `security` | OIDC settings, authentication and request identity |
| `operations` | Deployment configuration, resource limits and redacted observations |
| `web` | Shared route projection, error mapping, pagination and retained-domain admission |

Request schemas live in each context's `dtos.py`. Response mappers project persisted objects into the public response fields. Controllers validate HTTP input and call application services. Services enforce access and lifecycle rules, and repositories perform persistence operations through native pyfly Data.

Entities and repositories live in separate modules. The application reuses the same entity definitions for the API, workers and migrations, which keeps table metadata consistent. Migration execution remains a separate deployment operation with its own credentials.

## Agent configuration and conversations

`AssistantConfigurationService` owns provider and agent changes, connection validation and configuration revisions. `KnowledgeScopePolicy` checks requested knowledge against persisted access and the agent's allowed resources. `AssistantService` owns private conversations and generation requests and delegates configuration operations to the focused service.

The queue claims work with a lease. Each consumer has its own worker identity, and expired workers lose authority to change a run. Admission limits apply to a user's queued and running answers within an organization, across conversations and retries. Replaying the same accepted request returns its existing run. See [operator configuration](../operations/configuration.md) for deployment limits and observations.

`OrganizationChatService` owns the organization default independently of conversations. The standard frontend resolves this setting using its current authorized workspace/project; explicit headless requests still submit the chosen agent identity. Configuration never grants knowledge access.

## Original files and cloud transport

`packages/storage/src/koinon_storage` supplies typed Azure Blob Storage and Google Cloud Storage byte operations without importing the backend or either knowledge domain. The document, structured and attachment adapters retain their existing domain ports and keys. Optional provider SDKs and credentials are resolved lazily. PostgreSQL continues to own permissions, recorded digests, versions, expiry and provenance; the blob store owns the corresponding bytes.

For remote structured queries, the native executor materializes only registered pinned snapshots into bounded private temporary files before invoking DuckDB. Its SQL restrictions and disabled external access remain in force. See [storage configuration and limits](../operations/storage.md).

## Stable contracts during refactoring

Moving a module preserves the public HTTP paths, SDK request shapes, canonical principals and existing storage identities. Encrypted provider credentials carry a format version: existing credentials keep their original key derivation, while newly written credentials use the current version. Keep backward reads until an explicit credential rotation has completed.

Integrators should use the [typed SDK or public API](../guides/headless.md). Internal entity and repository imports are implementation details and can change independently of those public contracts.

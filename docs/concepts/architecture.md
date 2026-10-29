# How koinon fits together

Koinon has one application boundary and one native pyfly application context. The management application, embedded components and SDK call the same authorized API. Embedding a component does not embed a database, start a second backend or grant access to a tenant.

```mermaid
flowchart LR
  User[User] --> Shell[Angular management shell]
  Host[Host application] --> Components[Angular components or custom elements]
  Shell --> SDK[Unified typed SDK]
  Components --> SDK
  Server[Server-side consumer] --> SDK
  SDK --> Auth[OIDC authentication and persisted authorization]
  Auth --> API[Native pyfly controllers]
  API --> Catalog[Shared catalog and provenance]
  API --> Canon[Document knowledge domain]
  API --> Structured[Structured data domain]
  API --> Jobs[Durable jobs and audit]
  Catalog --> Data[Native pyfly Data and transactions]
  Canon --> Data
  Structured --> Data
  Jobs --> Data
  Data --> PG[(PostgreSQL)]
  Canon --> Adapters[Configured blob, search and vector adapters]
  Structured --> Adapters
  Canon --> Agentic[Native pyfly agentic runtime]
  Structured --> Agentic
```

The document and structured knowledge packages preserve established domain behavior, measured against retained regression suites and integrated acceptance checks. The product control plane owns shared identity, membership, catalog ancestry and the product API. Both domains must borrow native Data resources and the context-owned agent factory; they must not start an independent agent runtime or container.

Original files, processed artifacts and private conversation attachments use explicitly configured local, S3, Azure Blob Storage or Google Cloud Storage adapters. The independent storage package shares Azure/GCS transport across domain ports. Blob storage does not replace PostgreSQL metadata or authorization. Existing data stays bound to its recorded storage identity; changing a profile is a separately planned migration. See [file persistence](../operations/storage.md).

A source is distinct from its assets. One source may yield a document and a dataset. A document contains chunks with original section/page references. A dataset contains tables and immutable snapshots with schema and query provenance. A shared catalog identifier maps explicitly to the original domain identifier. Equal names never imply equal identities.

```mermaid
flowchart LR
  Tenant[Tenant] --> Workspace[Workspace]
  Workspace --> Project[Project]
  Project --> Collection[Collection or corpus]
  Collection --> Source[Source]
  Source --> Document[Document]
  Source --> Dataset[Dataset]
  Document --> Chunk[Chunk]
  Dataset --> Table[Table]
  Table --> Snapshot[Snapshot and schema]
  Source --> Index[Index version]
  Project --> Session[Query session]
  Session --> Evidence[Referenced chunks and snapshot pins]
```

Knowledge operations validate persisted membership and complete resource ancestry before calling a domain service. Selecting a tenant or workspace in a URL, header, component input or SDK call does not grant a privilege. A query's referenced datasets and tables must belong to the authorized context before execution.

Operational state lives in PostgreSQL. Vector extensions are provider choices, not a substitute for operational persistence. `pgvector` and `pg_vectorsearch` are distinct providers with different extension, type, index and parameter contracts. Enabling one must never silently select the other. A configured provider is reported separately from a qualified live connection.

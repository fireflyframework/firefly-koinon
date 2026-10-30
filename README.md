# firefly koinon

![firefly koinon](brand/repository-banner.svg)

Koinon keeps organizational documents and datasets in one knowledge library. People can find sources, maintain content and ask questions with supporting evidence. The backend uses native pyfly for application services, security, data access and agents.

Development and integrated qualification are in progress. There is no qualified product release yet. Existing installations continue to operate. Migration notices and repository archiving follow verified capability coverage, a tested migration path and a qualified release.

The API and durable workers run independently of the frontend. Typed Python, TypeScript and Java SDKs let Forge and other products add knowledge capabilities without installing Angular. Hosts that need an interface can use the Angular library or encapsulated custom elements.

PostgreSQL stores operational state, access grants, conversations and provenance. OIDC handles sign-in; persisted membership and scoped personal tokens control API access. Documents and datasets keep distinct identities and source bindings.

Original files, processed snapshots and private attachments support explicit local, S3, Azure Blob Storage and Google Cloud Storage profiles. See [storage configuration](docs/operations/storage.md) for provider installation, workload identity, bounds and the separate live-cloud acceptance requirements.

Read the [documentation](docs/index.md), [headless integration guide](docs/guides/headless.md) and [qualification record](docs/operations/qualification.md).

Code uses [Apache-2.0](LICENSE). Firefly names and marks remain protected trademarks; the code license grants no trademark rights.

Copyright 2026 Firefly Software Foundation. Made with ♥.

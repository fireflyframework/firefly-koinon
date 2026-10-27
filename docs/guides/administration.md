# Configure the organization

The administrator owns people, access and organization policy. The operator configures knowledge sources, providers, agents and processing. These roles keep routine operations separate from granting authority.

## Initial setup

1. Deploy database, identity integration and API using the [operations guide](../operations/local-deployment.md).
2. Bootstrap the organization and canonical administrator through the audited deployment command. Identity-provider login alone grants no product membership.
3. Create spaces and recognizable folders, then grant the smallest useful roles and scopes.
4. Configure storage, search/vector and model prerequisites. Validate them before importing knowledge.
5. Import a small fictional document and dataset. Verify processing, retrieval, schema, query evidence and failure recovery before onboarding the team.
6. Configure an agent, validate its provider/model and test with an end-user account.

## People and access

| Role | Intended work |
| --- | --- |
| Viewer | Browse knowledge, search and ask agents |
| Analyst | Viewer work and governed dataset questions |
| Editor | Maintain knowledge and submit imports |
| Operator | Configure providers/agents/sources/indexes, manage jobs and inspect audit |
| Administrator | Operator work, membership and identity/settings policy |

Memberships can apply organization-wide or to an authorized space. The last organization administrator cannot be removed. Revocation is checked on subsequent protected operations, including existing sessions. An operator cannot grant membership or change identity authority.

## Connections and parameters

Settings should present prerequisites and observed states. Model credentials are write-only; responses report whether they are configured. They are encrypted using an external master key and never stored in browser settings. Provider addresses require a deployment-managed host allowlist.

Database roles, identity endpoints, storage roots and extension installation remain deployment authority. Migration credentials and administrator secrets do not belong in organization settings. Distinguish deployment-managed parameters from tenant-level provider and agent configuration.

`pgvector` and `pg_vectorsearch` are separate adapters. Their extensions, dimensions, indexes and query parameters require validation against the selected provider. An installed extension does not establish that every retrieval or query path works.

Unsupported connections and missing credentials need setup guidance. Never report them as connected or create a successful placeholder import. The [qualification record](../operations/qualification.md) identifies the provider/deployment boundary actually exercised.

## Operate and recover

Activity presents observed processing state and recoverable errors. Audit records authority changes and operations. Retry refers to persisted work and its original scope. Back up database, identity state, source storage and encryption material with an explicit retention policy. Practice [restore](../operations/backup-restore.md) into a separate environment.

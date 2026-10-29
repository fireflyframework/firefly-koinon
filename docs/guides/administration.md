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

## Invite someone or change access

In **People & access**, search existing people by name before assigning a role. Choose the organization or a workspace as the scope. Filters and pages come from the server; changing the scope or filters returns to the first page. A person may hold several roles, so removing one assignment may leave access through another.

For someone new, create an invitation link with a role, scope and expiry. The default lifetime is 24 hours; the maximum is seven days. Copy the private link when it is created: its secret is shown once. No email is sent and no identity-provider account is provisioned. The recipient must sign in through the configured identity provider and explicitly accept. An invitation cannot replace an existing assignment in that scope. Revoking the link prevents redemption; after redemption, manage the resulting role assignment separately.

## Corporate access

Corporate connections preserve the deployment's canonical issuer and subject. Keycloak can broker an external directory while preserving those identities. Matching email addresses never merge accounts or grant access.

An explicit group mapping associates a directory group with a product role and optional workspace. Directory-managed grants remain separate from manual roles. Edit the mapping or upstream group to change a managed grant; manual membership operations cannot change it. Keep a manual organization administrator for recovery.

Connection activation requires a fresh sign-in by the initiating administrator, a complete authorized directory observation and the protected broker configuration. A saved connection or discovered group is insufficient. Changes invalidate the proof; disabling a connection removes its managed authority immediately. Normal group changes take effect when the bounded observation expires and refreshes. Failed or incomplete refreshes cannot retain expired managed access.

Corporate management screens and external Entra ID/Google Workspace activation are still under qualification. The current native Keycloak proof uses an isolated local realm. Deployment operators must supply directory permissions, encryption material and approved provider origins before activating a real connection.

## Knowledge model assignments

Providers and agents are separate from the model roles used by document and dataset processing. In **Knowledge models**, choose an organization default or an explicit workspace override, then assign the role described by the server. A disabled workspace override blocks fallback to the organization default.

Generative roles may use the current chat agent only when the role descriptor permits it and the operation has an active agent context. Embedding roles require an explicit provider, model, dimensions and approved existing space. Do not guess an embedding space or substitute a different model for indexed knowledge. An incompatible change requires reindexing; removing and recreating an assignment does not bypass that requirement.

## Knowledge approval

Dataset questions may retain execution, result and audit evidence. Canonical query credentials carry read/execute authority and cannot automatically create knowledge-base examples, including when the caller is an administrator.

Native automatic draft learning is disabled by default. An explicitly enabled `autolearn_enabled` policy also requires explicit example-author authority; query-read authority alone is insufficient. Authorized proposals retain `PROPOSED` status. Draft and rejected examples are excluded from lexical/vector grounding and versioned indexing until an authorized explicit approval makes them eligible. Approval computes the compatible embedding before changing review state, then publishes the active vector in the same transaction as the approval. Provider failures, a changed source or an active-index change leave the draft unapproved. Approval also compares a private database row version alongside source and review state. A rejection committed while embedding is in flight wins even if the example was already rejected; stale approval returns a conflict. The private version adds no public response field or schema column, and a fresh explicit reapproval remains supported. Existing drafts and vectors are preserved; they are not silently approved, deleted or backfilled.

## Connections and parameters

Settings should present prerequisites and observed states. Model credentials are write-only; responses report whether they are configured. They are encrypted using an external master key and never stored in browser settings. Provider addresses require a deployment-managed host allowlist.

Database roles, identity endpoints, storage roots and extension installation remain deployment authority. Migration credentials and administrator secrets do not belong in organization settings. Distinguish deployment-managed parameters from tenant-level provider and agent configuration.

`pgvector` and `pg_vectorsearch` are separate adapters. Their extensions, dimensions, indexes and query parameters require validation against the selected provider. An installed extension does not establish that every retrieval or query path works.

Unsupported connections and missing credentials need setup guidance. Never report them as connected or create a successful placeholder import. The [qualification record](../operations/qualification.md) identifies the provider/deployment boundary actually exercised.

## Operate and recover

Activity presents observed processing state and recoverable errors. Audit records authority changes and operations. Retry refers to persisted work and its original scope. Back up database, identity state, source storage and encryption material with an explicit retention policy. Practice [restore](../operations/backup-restore.md) into a separate environment.

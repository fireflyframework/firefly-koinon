# Organization chat default: editable source qualification

Copyright 2026 Firefly Software Foundation. SPDX-License-Identifier: Apache-2.0.

This record covers the editable source checkout on October 28, 2026. It does not claim release publication, an applied PostgreSQL migration, live configuration changes, model calls, or production acceptance.

The new organization setting persists one nullable default agent per tenant. `GET` accepts the current workspace/project context; `PUT` requires organization-level `agents:write`, an organization-wide agent and the expected revision. Atomic insert/update operations admit one winner for concurrent creation or revision updates. The record stores the actor and timestamp, and each successful update emits an audit event. Cleared, disabled, missing or subsequently scoped defaults never select another agent. The explicit run input and queue contract remain unchanged.

Native revision `koinon_0017_org_chat` follows `koinon_0016_authorized_apps`. A unique tenant/agent index and composite foreign key prevent cross-tenant defaults without rebuilding the agent table. The migration regression retains an existing agent and a referencing run. The source-only, unpublished bulk migration has been renumbered to `0018_bulk_admission.py`, revision `koinon_0018_bulk_admission`, with the new organization revision as its parent. Historical private qualification records were preserved. Only revision 17 belongs to this rollout; copying or applying the editable migration head would also include unpublished bulk schema.

The canonical contract contains 142 operations and 258 DTO schemas. The Python SDK exposes `organization_chat_settings` and `update_organization_chat_settings`; TypeScript exposes `organizationChat.get/update`; Java exposes `organizationChat(tenant).get/update`. Shared manifests, generated fields, typed Java APIs, fixtures and the API reference agree. Explicit null clearing, current revisions and declared scope filters survive SDK transport. Java response/input revision types are compatible, including in an external consumer.

| Verification | Result |
| --- | --- |
| Complete backend suite | 930 passed, 35 skipped |
| Focused settings service, HTTP/PAT and migration regressions | 7 passed |
| Dedicated PostgreSQL migration/FK/CAS suite | 4 passed |
| Deployment tests | 12 passed, 1 skipped |
| Python SDK source suite | 108 passed |
| Python SDK isolated installed wheel suite | 108 passed |
| TypeScript SDK source suite | 35 passed |
| Installed npm archive suite | 35 passed |
| Java SDK Maven verification | 852 passed |
| Java JAR external typed Java 21 consumer | Passed |
| Backend and Python SDK Ruff | Passed |
| Backend and Python SDK configured Pyright | Passed |
| TypeScript type check | Passed |
| Deterministic contract, generated DTO/API/fixtures and documentation checks | Passed |

Backend checks use the configured project commands with source imports for the native document, structured and shared storage packages. The first complete backend run encountered two active storage-profile test assertions; the storage owner corrected those assertions and the subsequent complete run passed. The initial settings creation and concurrent revision checks used private temporary SQLite databases. The dedicated PostgreSQL follow-up below closes migration, foreign-key and concurrent transaction semantics. Managed databases, PostgreSQL roles/memberships/grants, live services, providers and models were unchanged.

## Dedicated PostgreSQL follow-up

A fresh uniquely named database was restored from the preserved private v21 dump. Only the native history was advanced to explicit revision 16, then the opt-in suite applied exactly `koinon_0017_org_chat`; bulk revision 18 remained absent. The document and structured histories were unchanged. No existing clone or dump was replaced, and the original dump hash was revalidated after the run.

`backend/tests/web/test_organization_chat_postgres.py` requires the explicit `KOINON_ORGANIZATION_CHAT_POSTGRES_URL` opt-in, loopback port 18783, a dedicated `koinon_org_chat_qualification_` database name and an initial native16 restore. Each migration qualification run requires a new restore; the tests do not downgrade, reset or replay an existing fixture. `KOINON_ORGANIZATION_CHAT_POSTGRES_EVIDENCE` optionally selects a private sanitized observation file.

The four PostgreSQL tests passed. Migration preserved the complete row hashes of all 15 retained agents and 15 retained runs, their relationship and the existing run-to-agent foreign key. A valid same-tenant default committed, while a direct cross-tenant assignment failed with SQLSTATE 23503. First creation and subsequent revision updates used distinct PostgreSQL connections; the losing writer was observed waiting for the uncommitted winner, then received a conflict. Each successful CAS emitted exactly one audit event; concurrent losers and later stale submissions emitted none. The winning actor, aware timestamp, revision and explicit clear persisted.

Private URLs, restore/test logs, original-dump hash and sanitized observations are retained in the task's `work/runtime/organization-chat-postgres-*` fixture folder with 0600 files and a 0700 directory. The restore used `--no-owner --no-acl`, existing credentials and no PostgreSQL role, membership or grant changes. The existing migration login owns this dedicated fixture; these tests establish database transaction semantics and do not establish runtime-role least-privilege deployment acceptance. No application process was started and no model/provider operation was invoked.

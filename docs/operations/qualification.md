# Local qualification boundary

The owned local environment was checked with PostgreSQL 17.11, vector 0.8.7, Redis 8.2.3 and Keycloak 26.8.1. No shared service or global PostgreSQL installation was modified.

| Observed check | Result |
|---|---|
| Native and both preserved knowledge migration histories | Applied; native assistant revision included |
| Runtime PostgreSQL roles | Non-superuser, no RLS bypass; separate privileged provisioning roles |
| Document knowledge FORCE RLS | No scope hidden; foreign tenant hidden; matching scope visible; wrong-tenant insert rejected; local scope reset |
| Retained Structured knowledge service/repositories | Canonical workspace provision, conflicting tenant rejection, foreign/no-scope read denial, native outer transaction rollback |
| Real browser OIDC | Native state/PKCE/ID-token validation, canonical issuer/sub, cookie introspection |
| Session/bearer separation | Cookie-only API denied; real API access token accepted; wrong-audience ID token denied |
| Five fictional identity users | Expected tenant/role denials, editor write, last-admin protection, immediate membership revocation |
| CSRF and logout | Missing token denied; matching token logout; shared logout visible on both API instances |
| PostgreSQL sessions | Survived process restart; reused by two independent API processes |
| Redis | Authenticated ping and expiring write/read |
| Backup and restore | Private custom archive restored into a new database; three recorded revision heads and fictional tenants inspected |

These observations do not establish live external model/connector acceptance, frontend visual acceptance, Docker image execution, production load/capacity, a published release, or a production restore. Provider readiness must be tested against each configured endpoint/model. The Compose, systemd and proxy files are deployment templates; Docker was unavailable in the local qualification environment.

Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc. Licensed under Apache-2.0. Made with <3.

# Schema and role changes

Only a controlled migration process receives `KOINON_MIGRATION_DATABASE_URL`. API processes receive separate primary, Document knowledge runtime/control, and Structured knowledge runtime/control URLs. Each URL selects an explicit named native datasource. Runtime roles are neither superusers nor RLS bypass roles. The two control roles deliberately bypass RLS for narrowly scoped provisioning; arbitrary request-selected access must never use them.

The migration command takes a PostgreSQL advisory lock and upgrades three preserved histories with separate version tables: `koinon_native_version`, `koinon_canon_version`, and `koinon_structured_version`. Internal history labels stay stable for compatibility. Native revisions cover catalog/jobs, resource bindings, native SQL session/concurrency tables, and assistant/chat records. Runtime schema policy is `validate`; API startup does not generate production DDL.

```sh
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/provision_roles.py
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/migrate.py
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/provision_roles.py --grant
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/migrate.py --check
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/provision_roles.py --check
```

The initial operator must install vector/pgcrypto extensions and create roles. Restrict that authority to the migration job. Inherited role bootstrap now creates NOLOGIN roles without executable default passwords; generated runtime credentials are separate. The intentional patch and upstream hash are recorded in the Structured knowledge package provenance directory.

Provisioning refuses an existing role with conflicting superuser/RLS privileges. Review mismatches explicitly. Grants cover scoped table families/sequences, exclude migration-version tables and do not grant schema creation. Reapply grants after adding tables. `--check` verifies role boundaries; also verify application CRUD and RLS using runtime credentials.

An unqualified `alembic_version` table requires reviewed history mapping. Do not stamp, delete version rows or replay migrations to bypass this guard. This deployment does not automatically adopt a separate installation's data. Back up first, test the exact upgrade on a restored copy, then schedule migration and restart separately. Automatic downgrade is disabled; use a reviewed recovery plan.

Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc. Licensed under Apache-2.0. Made with <3.

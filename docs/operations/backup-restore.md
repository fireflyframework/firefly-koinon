# Backup and recovery

Use PostgreSQL 17 tools matched to the server. Set `KOINON_POSTGRES_BIN` when the tools are outside PATH. Run backup with migration/operator authority outside the API service:

```sh
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/backup.py /private/backups/koinon-2026-10-26.dump
backend/.venv/bin/python deploy/run.py --env-file /private/migration.env -- backend/.venv/bin/python deploy/restore_check.py /private/backups/koinon-2026-10-26.dump
```

Backup refuses an existing target and creates a mode-0600 custom-format archive. Credentials travel through the child process environment, not command arguments. Encrypt archives at rest and copy them to an independently protected destination. PostgreSQL dumps contain application data, audit records, sessions and encrypted provider credentials; they do not replace the external encryption master-key backup.

Restore checking creates a fresh uniquely named database and uses `pg_restore --no-owner --no-privileges --exit-on-error`. It never cleans or overwrites a database. It reports native/knowledge revision heads and tenant count; this is an initial integrity check, not complete application acceptance. Supply extension binaries first, then perform runtime-role grants, RLS tests and representative document/structured queries against that isolated database. The newly created database remains for inspection; removal requires an explicit operator decision.

Back up blob/object storage and its versioning policy consistently with metadata. Back up the identity database, realm/client settings and secret-manager recovery material separately. Redis AOF improves local durability but is not an independent backup. Define recovery-point/recovery-time objectives, scheduled archive verification, retention and access controls with your operator.

A local drill restored the owned application archive into a new database and checked all three revision histories plus two fictional tenants. A second drill included native revision `koinon_0003_assistants` and both current knowledge heads. Repeat the drill after release/schema changes. Do not restore over a retained deployment to test recovery.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.

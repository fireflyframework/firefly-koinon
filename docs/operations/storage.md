<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Files and storage

koinon persists original files as well as the knowledge extracted from them. An installation needs its database state, referenced objects and protected encryption material together to recover a complete repository.

## Know what is stored

| Store | Contents |
| --- | --- |
| Documents | Original versions, normalized artifacts and replay inputs tied to recorded source identities. |
| Structured data | Original dataset files, registered Parquet snapshots and retained query results. |
| Private chat files | Owner/conversation-scoped originals, normalized content and registered staging. |
| PostgreSQL | Ownership, permissions, catalog/version bindings, hashes, source text, indexes, jobs, conversations, audit, profiles and encrypted credentials. |

The three object stores can each use local storage, S3, Azure Blob Storage or Google Cloud Storage. They have independent profiles. Object storage does not replace PostgreSQL, and an index is not a backup of the originals.

## Find the right guide

| What you need to do | Read |
| --- | --- |
| Set up a new store, credentials or environment variables | [Configure storage providers](storage-configuration.md) |
| Understand durability, limits, shared mounts and cloud behavior | [Durability and limits](storage-behavior.md) |
| Move retained data or rehearse recovery | [Migration and recovery](storage-migration.md) |
| Connect an external enterprise document system | [ECM integration](ecm-integration.md) |
| Create and check database backups | [Backup and recovery](backup-restore.md) |

## Configure the installation

Storage belongs to protected deployment configuration. Organization administrators can inspect observations in **Settings**, under **Storage & indexing**; model-provider settings and personal API tokens do not change a bucket, container, mount or cloud identity.

For one machine, use private persistent volumes. Multiple instances need the same intended shared stores and database bindings; separate node-local directories do not provide shared storage. Provision cloud namespaces and their least required permissions before qualifying the deployment.

A valid profile and installed SDK establish configuration. Cloud availability remains unknown until separately observed. Check credentials, object reads/writes, private access, signing where required, and restoration against an owned test namespace before relying on a deployment.

## Change an existing store

Changing configuration does not copy files or rewrite historical snapshot URIs. Inventory and back up the complete state, prepare a fresh target, compare registered keys and exact bytes, then rehearse access and restoration before cutover. Both local attachment root bindings must agree when the retained compatibility setting is present. The [migration guide](storage-migration.md) gives the complete procedure.

## Bulk work remains separate

Use [durable source batches](../guides/bulk-intake.md) for queued originals up to 128 MiB each and 512 MiB per batch. The synchronous upload endpoint remains at most 32 MiB. A cloud adapter alone does not supply the native admission, lease, authorization or immutable publication contract. The [Library file profile](../reference/library-file-ingestion.md) records raw/expanded/object/parser bounds and the lifetime quota policy. Preserve every accepted receipt and reconcile unknown outcomes explicitly.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.

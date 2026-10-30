<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Migrate and recover stored files

Changing a storage root, bucket, container or prefix does not move existing knowledge. PostgreSQL identities/hashes and the referenced bytes form one recoverable state. Start with the [persistence overview](storage.md), [exact profiles](storage-configuration.md) and the operator's [backup/recovery procedure](backup-restore.md).

## Inventory the complete state

Record the qualified application/schema version and the effective binding for documents, structured objects and private attachments. Include backend, root or endpoint/bucket/container/prefix, selected identity policy, object count, exact lengths/hashes and referenced version/snapshot IDs. Keep secret values and signed URLs out of reports.

Preserve the database state for every configured datasource, including all three migration histories, owners, privileges, row-level policies, sequences and current bindings. Database content includes source text/projections, conversations, review/audit state, encrypted credentials and account data such as sanitized avatars; it is not merely an index. Preserve encryption-key recovery material separately. A database-only dump cannot recover object originals, and a bucket copy cannot reconstruct authorization or source/version relationships.

Distinguish durable originals/artifacts/snapshots/results from scratch files, private staging and provider-managed incomplete sessions. Include every configured external store in the operator's backup inventory. Do not infer a complete inventory from one directory size, one current head or a cloud bucket's versioning flag.

## Rehearse before switching a retained binding

1. Establish a maintenance boundary for the original writers and capture a consistent database/object-store recovery point. Coordinate API, conversation/index/attachment workers and any authorized external integration. Keep an independent protected backup.
2. Copy into a fresh owned target namespace. Preserve relative registered keys, original bytes, normalized/artifact bytes, Parquet objects and query-result objects. Do not reset the original, rename keys to filenames or merge into an unknown target prefix.
3. Compare complete object inventories, byte lengths and SHA-256 values. An ETag is not a universal content digest. Preserve source-version/extraction/part and table-snapshot identities, predecessor links and current-head pointers.
4. Restore databases into fresh target databases and validate the intended roles/ACLs/RLS as well as schema heads and row counts. Do not use a destructive restore, revision stamp or empty schema to make a drill appear successful.
5. Bind a new isolated application configuration to the copied stores and target databases. Match both local attachment root settings if the retained fallback exists. Keep active/original configuration and roots untouched while qualifying the target.
6. Exercise authorized and denied reads with current runtime roles. Read historical document bytes/parts, registered table snapshots and representative stored results, private originals/normalized files, and current membership/ownership checks. Compare returned identities/hashes and preserve explicit missing/expired history rather than filling it in.
7. Check parser/query scratch capacity, cancellation, owned-client disposal, object/session cleanup and recovery from an interrupted operation. Cloud IAM, KMS/signing, consistency and network behavior require their own owned-provider tests.
8. Switch only through the deployment's reviewed cutover procedure after parity is established. Keep a defined rollback binding and recovery point. A rollback must account for writes accepted after cutover; it is not blindly pointing at an older database or deleting the new target.

This describes operator work, not an executable migration command. There is no generic public “move every store” API. Native structured rows may retain absolute/native snapshot URIs: changing a bucket/prefix/root alone does not rewrite them. A URI rebinding migration needs separately reviewed target-only transformations and exact identity/byte parity. Reingesting a file creates new observations; it does not restore the old immutable identities or repair unknown provenance.

The private attachment store rejects a changed binding in a running instance. Local compatibility roots must also match before first binding. Fix the prepared target configuration and complete copy; do not weaken those guards or remove retained bytes to satisfy them.

## Retention and restoration

Cloud versioning, object lock, replication, encryption and lifecycle policy are deployment responsibilities. Retain keys and object generations required by the database recovery point. A lifecycle rule that expires a still-referenced original can leave valid metadata with unavailable content. Keep private attachment TTL/purge policy separate from long-lived shared source history and from backup retention.

Use registry-aware, authorized cleanup. Private purge addresses its registered original/normalized keys and bounded staging; do not run broad filename/prefix deletion over a durable store. Inspect temporary leftovers and abandoned cloud sessions after hard stops without treating them as permission to delete registered objects. Expired/unavailable source bytes remain unavailable in historical audit; the system must not fabricate a recovered source or mark incomplete lineage complete.

Restore checking must include current runtime-role reads and denial cases, exact bytes, active bindings and required encryption material. Provider credentials that can list objects are not proof that reads, writes, deletion, signing or restore are qualified. The [backup guide](backup-restore.md) owns the concrete database tooling; storage configuration does not replace it.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.

<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Durable bulk staging and deployment

Bulk staging is an independent private storage profile. Setting the final document,
attachment or dataset object store does not configure staged originals. Clients
supply bounded manifests and bytes; they cannot select object keys, containers,
filesystem paths, credentials or deployment worker settings.

## Independent container replicas

Use PostgreSQL plus a shared private Azure Blob or GCS namespace for independent API
and file-worker replicas. Every replica must select the same staging profile and
prefix. An immutable storage identity is recorded with each new attempt. A restart
with a different profile fails closed for retained originals; changing an endpoint
or copying a directory is not an implicit migration.

```yaml
koinon:
  knowledge:
    bulk:
      storage_backend: azure
      azure_account_url: https://your-account.blob.core.windows.net
      azure_container: private-bulk
      azure_prefix: staged-originals
      storage_request_timeout_seconds: 10
      upload_lease_seconds: 180
      recovery_lease_seconds: 90
      max_local_storage_operations: 8
```

Provision the private namespace and narrow runtime object permissions separately.
Azure uses the shared storage adapter's approved credential chain, including managed
identity when configured by the deployment. Do not put keys or SAS URLs into this
profile or client requests. GCS uses `storage_backend: gcs` with `gcs_bucket`, optional
`gcs_project` and `gcs_prefix`, and its deployment-managed credential chain. S3 bulk
staging is explicitly unsupported until its adapter has qualified conditional-create
semantics; a final-object S3 profile does not change that boundary.

Azure creates without overwrite; GCS uses generation-zero creation. Reads enforce
length/hash bounds and provider revision conditions. A different retained object at
an admitted key is a collision, never permission to overwrite it. API and worker
processes need only database/object connectivity, not a shared POSIX mount.

## Local compatibility

The default `storage_backend: local` retains `storage_root`. The root must already
exist, be an absolute canonical directory without symlinks, have mode `0700`, and
remain private to the service identity. Local writes publish create-only files with
atomic link and directory durability. Every consumer still needs access to that
same durable filesystem; a local or ephemeral container directory does not become
shared storage merely because database fencing is enabled.

The capability response reports `private_local_posix`, `private_azure_blob`, or
`private_gcs_object`, the corresponding topology, and
`primary_database_generation_lease`. Those describe the implementation contract,
not acceptance evidence for a particular deployment, identity, provider or restore.

## Writer ownership, retries and recovery

Each admitted attempt has its own immutable registered key. A short primary
transaction reserves its byte/concurrency budgets and creates an internal writer
owner token, generation and database-clock lease before reading the request body.
No database connection or row lock is held over body streaming or object SDK I/O.
Before writing and before selecting a winner, current authority, manifest identity
and the exact live writer generation are checked again. Tokens remain server-only.

A same-key replay never becomes a writer. It may return a verified receipt, or report
an unresolved original as pending. Explicit recovery first commits a new verification
generation that fences the old writer, then reads and verifies only its registered
object. A final primary transaction checks the verifier lease, current batch revision
and authority before publishing a receipt. A crashed recovery retains its pending
action; the same key may resume read-only verification after its verifier lease
expires. It cannot reset attempt/action limits or replay an upload.

When logical admission is full, bounded metadata maintenance fences expired writer
or verifier generations and releases only their own logical permits. This performs
no object I/O and infers no successful original. Uncertain originals still require
explicit recovery. Existing winners and native receipts remain immutable.

Lease expiry does not prove physical SDK termination. A stale operation can finish
only at its own immutable attempt key, leaving accounted-for orphan bytes; its late
finish or cleanup cannot publish or release a newer operation's permit. The process
also bounds live body/write owners and SDK operations independently. Cancellation
drains admitted SDK work; shutdown rejects new staging I/O and drains owned calls.
Socket timeouts are not hard process deadlines. Budget physical overlap across
replica maxima, overlapping revisions and the platform's shutdown grace period.

The HTTP body has an admitted-size bound and a 60-second deadline. Choose upload and
verification leases to cover normal body/transport/verification budgets with margin.
A 32 MiB body may have more than one in-memory copy; do not size container memory from
one copy or assume a logical lease cancels a blocked thread. Cloud multipart or
resumable sessions also require provider lifecycle policy.

Configure [ingestion resources](ingestion-resources.md) separately from staging and
query execution. Object storage does not remove parser memory or local scratch.

## Retention and rollout

Apply the additive primary/structured migrations and narrow role grants before
activation. Stop old descriptor-lock bulk executors before enabling the database
fence; they do not understand its tokens. Verified legacy local originals remain
readable locally. Unfinished legacy rows have no recreated writer authority and need
a reviewed cutover. A cloud worker cannot silently reinterpret a legacy local key;
transfer original bytes, their registered locator and integrity evidence explicitly.

Byte reservations include uncertain, missing and late attempt objects. The published
reservation counter remains monotone; current defaults allow 1 GiB retained staging
per tenant and four admitted attempts per item. There is no automatic quota credit
or deletion workflow. Plan capacity and retention accordingly. A future append-only
release ledger must prove actual retired staging, a provider barrier against late
writers and independent preservation of authoritative originals before issuing a
credit. Expiry or one negative object read is insufficient.

An uncertain native operation stays inspectable as `reconciling`. Recovery never
automatically replays parsing, embeddings, model work or query execution whose outcome
is unknown. Preserve originals, manifests, native receipts and failures. Do not reset
counters or jobs to make a batch appear successful.

Qualify the installed artifact and actual managed deployment separately from source
and emulator tests: independent processes without shared local directories, process
loss before/after persistence and fencing, delayed SDK completion, current-authority
revocation, scale/rollout overlap, provider throttling, byte budgets and restore.

## Independent query worker

The [query-batch lifecycle](../guides/bulk-queries.md) uses primary manifests and native structured query-operation receipts rather than file staging. It has its own disabled-by-default `koinon.knowledge.bulk.query_worker_enabled` switch and native entry point `python -m koinon.knowledge.bulk_queries.worker`. File intake uses `koinon.knowledge.bulk.worker_enabled` or the dedicated `python -m koinon.knowledge.bulk.worker` entry point. The general job worker claims neither kind.

Both workers share the configured global/per-tenant concurrency budgets, native lease generation checks, owned-child kernel deadline and cleanup reserve. An expired lease does not authorize replay of an admitted unknown query. Preserve native markers and result objects alongside the primary database. Apply the reviewed primary and structured additive migrations and narrow role grants before enabling either worker; clients cannot enable workers or choose deployment credentials through a batch request.

# File persistence and shared private storage

Koinon retains original documents and dataset files. Document lineage also retains raw, merged and normalized artifacts; structured ingestion retains Parquet snapshots and query-result objects. PostgreSQL stores catalog bindings, metadata, hashes, versions and job state. Private chat attachments have a separate original/normalized blob store with SQL ownership, expiry and parsing state.

Existing document and structured storage configuration remains unchanged. The production example uses explicit local roots. Private attachments now select a typed local or S3 profile under `koinon.storage.attachments`. The default remains local; an absent private root never creates an implicit temporary store.

```yaml
koinon:
  storage:
    attachments:
      backend: local
      root: /var/lib/koinon/private-attachments
      max_object_bytes: 67108864
      request_timeout_seconds: 10
```

Existing deployments may keep `koinon.attachments.storage_root` with no new profile. That root remains the fallback. If both local root settings are present, they must identify the same path; conflicting roots fail rather than silently switching retained data. Never replace an existing library with an empty directory. Changing a running instance's bound storage location is rejected; plan a separate reviewed data migration when changing backends or roots.

Local roots must be real directories with owner-only 0700 permissions and owner read/write/traversal. New roots are created with those permissions; existing public or read-only directories are rejected and are not chmodded. Writes use a temporary sibling, file fsync, atomic replacement and directory fsync. Admission verifies the intended digest before writing and rereads persisted bytes with a bound before succeeding. Reads always check the SQL-recorded byte length and SHA-256. Purge addresses only the registered original/normalized keys and bounded registered staging cleanup.

The key format remains unchanged: an opaque hash of tenant, canonical user and thread, followed by the attachment UUID and `original` or `normalized`. Root paths and user-provided filenames are not object keys. Two service instances can read the same admitted keys when they use the same mounted directory; ordinary node-local directories are not shared storage.

For S3, install the backend `storage-s3` extra and configure an existing private bucket:

```yaml
koinon:
  storage:
    attachments:
      backend: s3
      s3_bucket: your-existing-private-bucket
      s3_prefix: koinon/private-attachments
      s3_region: your-region
      request_timeout_seconds: 10
      max_object_bytes: 67108864
```

An optional `s3_endpoint_url` supports an explicitly configured S3-compatible service; HTTPS is required outside loopback development, and credentials/query strings are forbidden in that URL. Optional `s3_kms_key_id` selects an existing KMS key; otherwise writes request AES256 server-side encryption. The adapter uses the standard boto3 credential chain, so deployment identity, workload identity or an external secret store should supply credentials. Configuration never stores access keys or secret keys. All instances must use the same bucket, prefix and provider policy.

The adapter does not create buckets, change access policies, set public ACLs, generate public URLs, list unrelated objects or probe a provider at startup. Provision private access, encryption, retention and any KMS permissions through the deployment's existing administration process. Grant only required object read/write/delete permissions for the configured prefix. A bucket configured as public elsewhere remains an operator error; object encryption does not establish private access policy.

S3 admission adds content digest/size metadata and a SHA-256 checksum, then verifies a bounded read. Reads request a byte range and also enforce the application limit, closing provider streams on success, oversize and failure. SDK connect/read timeouts are bounded and attempts are capped at two. These are SDK/socket limits, not a hard process cancellation guarantee for threaded SDK calls. No object write is acknowledged by Koinon's attachment lifecycle until digest verification succeeds. The current attachment path remains whole-byte and capped at 64 MiB; this is not a resumable large-file upload implementation.

Explicit environment aliases override matching file fields:

| Alias | Profile field |
|---|---|
| `KOINON_ATTACHMENT_STORAGE_BACKEND` | `backend` |
| `KOINON_ATTACHMENT_STORAGE_ROOT` | `root` |
| `KOINON_ATTACHMENT_STORAGE_S3_BUCKET` | `s3_bucket` |
| `KOINON_ATTACHMENT_STORAGE_S3_PREFIX` | `s3_prefix` |
| `KOINON_ATTACHMENT_STORAGE_S3_ENDPOINT_URL` | `s3_endpoint_url` |
| `KOINON_ATTACHMENT_STORAGE_S3_REGION` | `s3_region` |
| `KOINON_ATTACHMENT_STORAGE_S3_KMS_KEY_ID` | `s3_kms_key_id` |
| `KOINON_ATTACHMENT_STORAGE_REQUEST_TIMEOUT_SECONDS` | `request_timeout_seconds` |
| `KOINON_ATTACHMENT_STORAGE_MAX_OBJECT_BYTES` | `max_object_bytes` |

An absent alias preserves the configured value. Other attachment limits remain under `koinon.attachments`: file/image/thread quotas, selection count, extraction budgets, expiry and worker enablement. Provider storage does not bypass owner/thread authorization, current memberships, originating-token restrictions, lease fences or purge/expiry policies.

Local cross-instance tests and mocked S3 protocol tests qualify key preservation, bounds, atomic failure behavior, stream closure and configuration. They do not prove production cloud permissions, actual multi-node mounts, provider consistency, backup/restore, external workers or end-user acceptance. Complete those checks against explicitly owned test storage before declaring a deployment qualified. Back up registered blobs together with database state and external encryption keys; a PostgreSQL dump alone cannot recover originals.

Attachment observations distinguish optional `configured` (default false) from nullable `available` health. Local storage becomes configured after its privacy/access checks. S3 becomes configured only when the profile is valid and the declared SDK is installed; its health remains unknown until independently qualified. SDK presence is checked without creating a client or looking up credentials. A configured adapter permits an upload attempt once the database and worker prerequisites are observed, while the provider-health state remains visible as unknown. A missing SDK is unavailable. Python, TypeScript and Java contracts retain the optional field; the previous Java two-argument constructor remains supported.

## Bulk work remains separate

Canonical library upload currently accepts one file up to 32 MiB and executes ingestion in that request. It is not a durable bulk import contract. The retained structured package has bulk handlers, but exposing them would not supply canonical authorization, atomic admission or distributed backpressure automatically.

The next bulk contract should admit a bounded manifest with required idempotency key and request digest, stage immutable originals, persist stable batch/item IDs, then return 202. Leased workers should process bounded items/stages, preserve actor/token identity, recheck authority before publication, fence stale attempts and retry only incomplete items. Status must distinguish queued/running/succeeded/failed/cancelled and support authorized per-item retry/cancel with partial success. Query batches need their own item, concurrency, result-size, time and provider budgets while retaining read-only SQL and evidence. No large-scale throughput claim follows from the storage adapter alone.

Provider behavior follows the [official S3 GetObject contract](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html). No cloud operation is performed by reading this guide or loading configuration.

The retained structured S3 streaming writer aggregates input into 5 MiB parts, permits a smaller final part and stops before the 10,001st part. It attempts multipart abort on stream, upload, completion or cancellation failure while preserving the original error; provider lifecycle cleanup remains necessary if abort itself fails. Empty streams use a normal empty-object write. Protocol tests cover small and large chunks, failure and cancellation. These rules follow the [official multipart limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html) and [abort contract](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/abort_multipart_upload.html); they do not establish live cloud acceptance. Other retained provider adapters and whole-file ingestion limits remain separate qualification work.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.

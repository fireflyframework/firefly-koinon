<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Durability, limits and shared storage

koinon retains original documents and dataset files. Document lineage also retains raw, merged and normalized artifacts; structured ingestion retains Parquet snapshots and query-result objects. Private chat attachments have a separate original/normalized blob store with SQL ownership, expiry and parsing state.

| Durable state | Responsibility |
| --- | --- |
| Document store | Original versions, normalized/artifact bytes and replay inputs bound to recorded source/version/extraction identities. |
| Structured store | Original files, registered table snapshots and stored query-result objects. |
| Private attachment store | Registered owner/thread-scoped original and normalized bytes, including bounded staging. |
| PostgreSQL datasources | Catalog/permission bindings, hashes, versions, source text/projections, native indexes, jobs, conversations, review/audit records and account data such as sanitized avatars and encrypted credentials. |

Recoverable knowledge needs both the database state and its referenced bytes, plus separately protected encryption material. A metadata dump is not a file backup, and a bucket copy is not an authorization/lineage restore. See [exact configuration for all four backends](storage-configuration.md), [storage migration](storage-migration.md) and [ECM integration](ecm-integration.md) and [backup/recovery](backup-restore.md).

All three domains support local storage, S3, Azure Blob Storage and Google Cloud Storage. The production example retains explicit local roots. Cloud configuration is opt-in and does not move existing data. Private attachments select their own profile under `koinon.storage.attachments`; an absent private root never creates an implicit temporary store.

The local document selector is `localfs`; structured/private profiles use `local`. S3 structured storage uses a native `s3://bucket/prefix` root, while document/private profiles have separate bucket/prefix fields. See the configuration guide before copying fields across domains. A valid profile, installed SDK, live provider access, restore success and workload throughput are separate observations.

## Temporary processing in containers

Private attachment parsing uses a fresh owner-only temporary directory for each bounded child process. Python selects its temporary root from the process environment, including `TMPDIR`. Mount a writable, capacity-limited scratch volume there when the application filesystem is read-only. The parser removes its directory after success, failure or cancellation; an ungraceful container termination may leave scratch for the container platform to discard. Do not include scratch in backups or use it as the original-file store.

Cloud-backed parsing requires no local attachment storage root and never writes parser files into the application directory. Originals, normalized content and their SQL records remain in their configured durable stores. Replacing a container may discard scratch; it must preserve those stores and their encryption material. This separation does not establish cross-replica job recovery or a distributed bulk-upload contract.

## Private attachment local and S3 storage

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

## Azure Blob Storage and Google Cloud Storage

Install the backend from the repository root with `uv sync --project backend --locked --extra storage-azure` or `uv sync --project backend --locked --extra storage-gcs` before selecting a provider. Both extras can be installed together. Native document and structured distributions expose the same optional extras. The independent `firefly-koinon-storage` package supplies the shared byte transport; it imports no backend, database or model code. SDKs, clients and credentials are resolved only when an object operation is requested. Configuration and capability observations do not contact cloud providers.

Each domain is independent. Use `documents`, `structured` or `attachments` under `koinon.storage` with the following Azure profile, choosing a separate prefix for each domain:

```yaml
koinon:
  storage:
    documents:
      backend: azure
      azure_account_url: https://your-account.blob.core.windows.net
      azure_container: your-existing-private-container
      azure_prefix: koinon/documents
      request_timeout_seconds: 10
      max_object_bytes: 67108864
    structured:
      backend: azure
      azure_account_url: https://your-account.blob.core.windows.net
      azure_container: your-existing-private-container
      azure_prefix: koinon/structured
    attachments:
      backend: azure
      azure_account_url: https://your-account.blob.core.windows.net
      azure_container: your-existing-private-container
      azure_prefix: koinon/private-attachments
```

Azure uses `DefaultAzureCredential` from `azure-identity`: use managed identity, workload identity or externally managed environment credentials. Existing containers must already exist. The adapter does not provision containers, change policies or introduce a default account key. An explicitly configured loopback HTTP account may use anonymous protocol fixtures; an authenticated emulator can supply its connection string through the retained native structured adapter. Cloud account URLs require HTTPS and forbid embedded credentials, query strings and fragments. Existing structured `azure://container/prefix` roots remain supported with an explicit account URL or an externally supplied `AZURE_STORAGE_CONNECTION_STRING`; conflicting account bindings must not be used.

The corresponding GCS profile uses these fields for any of the three domains:

```yaml
koinon:
  storage:
    documents:
      backend: gcs
      gcs_bucket: your-existing-private-bucket
      gcs_project: your-project
      gcs_prefix: koinon/documents
    structured:
      backend: gcs
      gcs_bucket: your-existing-private-bucket
      gcs_project: your-project
      gcs_prefix: koinon/structured
    attachments:
      backend: gcs
      gcs_bucket: your-existing-private-bucket
      gcs_project: your-project
      gcs_prefix: koinon/private-attachments
```

GCS uses application-default credentials, including workload identity and externally supplied `GOOGLE_APPLICATION_CREDENTIALS`. No credential file contents enter the storage profile. `gcs_project` is optional for an existing bucket. An optional `gcs_endpoint_url` selects an explicitly configured emulator or HTTPS endpoint; anonymous access is enabled only for an explicit loopback endpoint. Ambient `STORAGE_EMULATOR_HOST` or `API_ENDPOINT_OVERRIDE` values cannot silently select a different endpoint. Existing structured `gs://bucket/prefix` roots remain supported. Explicit provider bucket/container and prefix fields determine the corresponding native snapshot URI; local roots retain their prior interpretation.

Environment aliases use `KOINON_DOCUMENT_STORAGE_`, `KOINON_STRUCTURED_STORAGE_` or `KOINON_ATTACHMENT_STORAGE_` followed by:

| Suffix | Profile field |
|---|---|
| `BACKEND` | `backend` (`azure` or `gcs`) |
| `AZURE_ACCOUNT_URL` | `azure_account_url` |
| `AZURE_CONTAINER` | `azure_container` |
| `AZURE_PREFIX` | `azure_prefix` |
| `GCS_BUCKET` | `gcs_bucket` |
| `GCS_PROJECT` | `gcs_project` |
| `GCS_PREFIX` | `gcs_prefix` |
| `GCS_ENDPOINT_URL` | `gcs_endpoint_url` |
| `REQUEST_TIMEOUT_SECONDS` | `request_timeout_seconds` (1–60, default 10) |
| `MAX_OBJECT_BYTES` | `max_object_bytes` (1–67,108,864, default 67,108,864) |

Aliases override only the matching profile field. Native environment settings use their existing document/structured configuration prefixes with `OBJECT_STORE_` followed by these provider field names. Document selection uses `OBJECT_STORE_BACKEND`; structured selection uses `OBJECT_STORE`. No application secret or credential is embedded in these examples.

Cloud writes preserve the existing opaque tenant/workspace/version keys and private attachment owner/thread keys. Prefixes are relative, and absolute keys, traversal, empty segments and credential-bearing endpoints are rejected. Azure creates block blobs with `overwrite=False`; GCS writes use `if_generation_match=0`. A repeated key succeeds only after its exact persisted length and SHA-256 match the requested bytes. A differing object is retained and the write fails. New objects carry `sha256` and `bytes` metadata, which reads recheck when present. Legacy objects without this metadata retain their existing caller-owned integrity checks; the adapter does not invent historical digest evidence.

Reads check provider-reported size before requesting a bounded range and enforce the returned length. Azure reads pin the observed ETag and GCS reads pin the observed generation. SDK request/socket timeouts are explicit and transport retries are disabled for these providers; durable callers may retry the same immutable key. Azure writes fit in one bounded block-blob request. GCS uploads through 8 MiB use the SDK multipart request; larger admitted objects use an SDK-created resumable session followed by one bounded transfer. Failed transfers attempt a bounded session abort while preserving the original failure. Session URLs are treated as private bearer capabilities and never exposed. Cancellation drains the in-flight threaded operation before propagating, including repeated cancellation. These socket bounds do not promise hard process deadlines or cancel identity-provider resolution. A completed cloud object can remain after a cancelled caller, so the immutable key and retry verification are required. Provider lifecycle cleanup remains necessary if session abort fails.

Structured input iterators stop before exceeding the configured object bound and have a bounded collection deadline. This is a bounded whole-object implementation, not an unlimited streaming ingestion API. Metadata listings cap results at 10,000. Signed downloads remain subject to the configured TTL and require a deployment identity capable of signing (Azure user delegation or GCS signing credentials); signing failures do not fall back to public URLs. Private attachment operations do not sign or list objects.

For governed structured queries, only registered pinned snapshot URIs under the configured Azure/GCS binding are downloaded through the native store. Each execution uses a fresh private temporary directory and 0600 snapshot files; table count is capped at 128 and aggregate scratch bytes are capped by `max_object_bytes`. DuckDB keeps external access disabled and reads only those temporary paths. Scratch files are removed after success, failure or cancellation. There is no shared cache: repeated query attempts reread their pinned cloud objects. Existing local and S3 execution paths retain their prior behavior.

Capability observations report a valid profile and installed SDK as `configured=true`, with cloud `available=null` until provider access has been independently observed. Missing SDKs are unavailable. These states do not establish live credentials, private access policy, replication, availability or restoration. Grant only required object permissions for the configured prefixes; signed structured downloads may require additional signing/delegation permissions. Back up registered blobs together with their database bindings and encryption keys.

Controlled provider tests and actual SDKs against fixture-owned loopback HTTP cover immutable writes, collisions, metadata/range reads, errors, cancellation, large GCS session completion/abort, native factory bindings and governed DuckDB execution over real Parquet. They do not qualify Azure/GCS accounts, IAM, workload identities, KMS, regional behavior, real emulator conformance, backup/restore, provider availability or production throughput. Acceptance still requires explicitly owned cloud endpoints and test credentials.

The implementation follows the [Azure block-blob create and download contract](https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobclient), [GCS generation preconditions](https://cloud.google.com/storage/docs/request-preconditions) and [GCS resumable session contract](https://cloud.google.com/storage/docs/performing-resumable-uploads). Loading configuration performs no provider operation.

## Temporary files during structured intake

Structured intake stores the original in the configured object store before handing its local working copy to the parser. The asynchronous worker loads that durable original when it needs to process the file; it does not depend on a temporary path from the upload request. Removing a working copy does not remove the registered original, its metadata or a published snapshot.

The current candidate reserves unique Parquet working files with owner-only `0600` permissions. CSV, JSON and spreadsheet conversion preserve those permissions when DuckDB writes the output. Column renaming uses its own private sibling file. The parser owns incomplete and skipped outputs; a successful return transfers only the files needed by subsequent stages. Each consumer cleans up after it finishes, including failure and cancellation paths. A failed section does not remove a running sibling's input. Cleanup attempts continue for independent parsed outputs if removal is denied; the denied file may remain and require operator attention.

Cancellation waits for an active native reader to finish before releasing the paths it uses. Shutdown timeouts are therefore soft while that operation drains. Configure a process supervisor for a hard shutdown deadline and an installation-owned private temporary directory for working files. Abrupt process termination can leave local files behind; automatic cleanup after a hard stop and Windows behavior have not been qualified. Never point a temporary-file cleanup job at the durable storage roots.

These lifecycle changes have source regression coverage. Their inclusion in the candidate does not establish deployment to an existing installation; the [qualification record](qualification.md) distinguishes source checks from managed rollout.

## Bulk work remains separate

Canonical library upload currently accepts one file up to 32 MiB and executes ingestion in that request. It is not a durable bulk import contract. The retained structured package has bulk handlers, but exposing them would not supply canonical authorization, atomic admission or distributed backpressure automatically.

For multiple files, bound the caller's queue and per-file bytes, process explicitly authorized destinations, persist each accepted receipt and reconcile ambiguous outcomes before advancing. Do not replay an entire list after a timeout or assume a plain upload has idempotency. Query batches also need caller-owned item, concurrency, result-size and time budgets while retaining read-only SQL and evidence. No durable bulk-import, automatic recovery or large-scale throughput claim follows from the storage adapter alone. See the [Python](../guides/python-knowledge.md), [TypeScript](../guides/typescript-knowledge.md) and [Java](../guides/java-knowledge.md) content-management guides.

Provider behavior follows the [official S3 GetObject contract](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/get_object.html). No cloud operation is performed by reading this guide or loading configuration.

The retained structured S3 streaming writer aggregates input into 5 MiB parts, permits a smaller final part and stops before the 10,001st part. It attempts multipart abort on stream, upload, completion or cancellation failure while preserving the original error; provider lifecycle cleanup remains necessary if abort itself fails. Empty streams use a normal empty-object write. Protocol tests cover small and large chunks, failure and cancellation. These rules follow the [official multipart limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html) and [abort contract](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/abort_multipart_upload.html); they do not establish live cloud acceptance. Azure/GCS use the bounded whole-object paths described above; whole-file ingestion limits remain in force.

Copyright 2026 Firefly Software Foundation. Licensed under Apache-2.0. Made with <3.

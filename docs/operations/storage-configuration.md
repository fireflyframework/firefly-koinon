<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Configure document, structured and private storage

Storage location and cloud identity are deployment configuration. A personal API token, organization administrator role or model-provider credential cannot change a bucket, container, mount or cloud IAM policy. API callers use authorized content operations; operators configure the byte stores used by the API and workers.

Read the [persistence overview](storage.md) before changing an existing installation. Configuration selects a binding; it does not copy retained objects or rewrite historical database references. Use the [migration and ECM guide](storage-migration-ecm.md) for that separate work.

## Choose the domain and backend

| Domain | File prefix | Local selector | Cloud selectors | Stored data |
| --- | --- | --- | --- | --- |
| Documents | `koinon.storage.documents` | `localfs` | `s3`, `azure`, `gcs` | Original versions, normalization/artifact bytes and replay inputs. |
| Structured | `koinon.storage.structured` | `local` | `s3`, `azure`, `gcs` | Original files, registered Parquet snapshots and query-result objects. |
| Private chat files | `koinon.storage.attachments` | `local` | `s3`, `azure`, `gcs` | Owner/thread-scoped originals, normalized bytes and registered staging. |

These are independent profiles. Choose distinct roots or prefixes and bind every reader/worker to the same intended profile. PostgreSQL remains required for ownership, versions, text/projections, catalog bindings, jobs and indexes; cloud objects do not replace those databases.

## Install the required optional dependencies

Use the release's qualified Python 3.13 environment and locked dependencies. For a private distribution, install the chosen extras from the operator's verified wheelhouse; source/package qualification does not imply public registry publication.

| Use | Declared package extras |
| --- | --- |
| Local stores | No cloud extra. |
| Document/private S3 | Backend `firefly-koinon[storage-s3]` provides boto3; native document distribution also declares `firefly-koinon-documents[s3]`. |
| Structured S3 | Also install `firefly-koinon-structured[s3]` for aiobotocore/botocore. Backend `storage-s3` alone does not supply this extra. |
| Azure across all three domains | Backend `firefly-koinon[storage-azure]`, backed by `firefly-koinon-storage[azure]`. Native document/structured packages also expose `storage-azure`. |
| GCS across all three domains | Backend `firefly-koinon[storage-gcs]`, backed by `firefly-koinon-storage[gcs]`. Native document/structured packages also expose `storage-gcs`. |

The native document package's separate `azure` extra concerns Azure model identity; use `storage-azure` for blob storage. Installing an SDK does not establish valid credentials, IAM, an existing container or live provider health.

## Local persistent volumes

```yaml
koinon:
  storage:
    documents:
      backend: localfs
      root: /var/lib/koinon/documents
      store_originals: true
    structured:
      backend: local
      root: /var/lib/koinon/structured
      presign_ttl_seconds: 86400
    attachments:
      backend: local
      root: /var/lib/koinon/private-attachments
      request_timeout_seconds: 10
      max_object_bytes: 67108864
  attachments:
    # Retained compatibility setting; omit if this deployment never used it.
    storage_root: /var/lib/koinon/private-attachments
```

Mount these paths on persistent storage, with the same contents and paths visible to the API and applicable workers. A process-local directory in two containers is not shared storage. Mount failure must not be mistaken for an empty library. Keep scratch space on a separate private, capacity-bounded temporary volume; temporary cleanup must never target these durable roots.

The private attachment root must be a real directory, not a symlink, with owner-only `0700` permissions and owner read/write/traversal. Existing insecure roots are rejected without chmod. Restrict the native document/structured volumes to the service identity too, but their retained local adapters do not enforce the same privacy/fsync contract automatically.

`store_originals: true` is required by immutable document intake. Disabling it makes that intake fail closed; it is not a harmless way to reduce storage while retaining full historical replay.

### Keep both attachment root bindings consistent

`koinon.storage.attachments.root` takes the profile location; `koinon.attachments.storage_root` is the retained fallback. If both local values exist, their expanded absolute paths must compare equal. Changing only the profile or its environment alias while the retained fallback still points elsewhere produces a root-conflict error. Update both bindings in a reviewed target configuration after preparing the complete target store. Do not remove the check, clear a retained store or substitute an empty directory to make startup succeed.

A bound attachment profile cannot change in a running instance. A restart with a new binding still requires a separately qualified migration, not just edited configuration.

## S3

```yaml
koinon:
  storage:
    documents:
      backend: s3
      s3_bucket: koinon-private-data
      s3_prefix: koinon/documents
      s3_region: us-east-1
      store_originals: true
    structured:
      backend: s3
      root: s3://koinon-private-data/koinon/structured
      presign_ttl_seconds: 86400
    attachments:
      backend: s3
      s3_bucket: koinon-private-data
      s3_prefix: koinon/private-attachments
      s3_region: us-east-1
      request_timeout_seconds: 10
      max_object_bytes: 67108864
```

Use an existing private bucket and the standard AWS credential chain: workload/instance role, web identity, an externally managed profile or secret-injected SDK environment. Storage profiles contain no access-key/secret-key fields. Do not put keys or signed query parameters in endpoint URLs.

Document/private profiles support `s3_endpoint_url` for an explicitly selected S3-compatible endpoint. The product bootstrap requires HTTPS outside loopback. Private attachments additionally support `s3_kms_key_id`; they request SSE-KMS when set and AES256 server-side encryption otherwise. Native document/structured S3 paths do not inherit this private adapter's encryption setting; establish bucket encryption and required key access through deployment policy.

The structured S3 profile uses the `s3://bucket/prefix` root. Its shipped factory passes the root and signing TTL to the retained adapter; it does not expose the document/private profile's separate endpoint, region or KMS fields. Do not invent `s3_bucket`, `s3_endpoint_url` or credential keys under this structured profile and expect them to configure that factory.

The retained structured adapter performs `head_bucket` and attempts `create_bucket` after a head failure. Pre-provision and qualify the intended bucket and metadata permissions; do not grant bucket provisioning authority merely to work around denied access. The document/private S3 adapters do not provision buckets. Native document S3 constructs a boto3 client when its store is built, so credential-chain resolution may occur then. Private S3 resolves its client lazily. These distinctions matter for startup, IAM and emulator qualification.

## Azure Blob Storage

```yaml
koinon:
  storage:
    documents:
      backend: azure
      azure_account_url: https://storageaccount.blob.core.windows.net
      azure_container: koinon-private-data
      azure_prefix: koinon/documents
      store_originals: true
    structured:
      backend: azure
      azure_account_url: https://storageaccount.blob.core.windows.net
      azure_container: koinon-private-data
      azure_prefix: koinon/structured
      presign_ttl_seconds: 86400
    attachments:
      backend: azure
      azure_account_url: https://storageaccount.blob.core.windows.net
      azure_container: koinon-private-data
      azure_prefix: koinon/private-attachments
      request_timeout_seconds: 10
      max_object_bytes: 67108864
```

Replace the account/container names with an existing private binding. All three domains use `DefaultAzureCredential` with this explicit account URL. Supply managed/workload identity or externally managed SDK environment credentials; any client secret belongs in the deployment secret store, not this YAML, an API token or a model prompt. The profile exposes no `azure_client_secret` or inline account-key setting.

The retained structured `azure://container/prefix` form also supports its native account URL/connection-string fallback. `AZURE_STORAGE_ACCOUNT_URL` and `AZURE_STORAGE_CONNECTION_STRING` are SDK/native compatibility inputs when the explicit account is absent; a connection string must identify that same account. This is not a general connection-string field shared by all three product profiles. Prefer an explicit account URL with workload identity.

Containers are not created by these Azure adapters. Cloud account URLs require HTTPS without userinfo, query strings or fragments. Anonymous protocol fixtures are restricted to explicit loopback endpoints; an emulator test is not Azure account/IAM acceptance. Native structured signing may require user-delegation/signing authority beyond object reads; a signing failure never becomes a public download.

## Google Cloud Storage

```yaml
koinon:
  storage:
    documents:
      backend: gcs
      gcs_bucket: koinon-private-data
      gcs_project: your-project-id
      gcs_prefix: koinon/documents
      store_originals: true
    structured:
      backend: gcs
      gcs_bucket: koinon-private-data
      gcs_project: your-project-id
      gcs_prefix: koinon/structured
      presign_ttl_seconds: 86400
    attachments:
      backend: gcs
      gcs_bucket: koinon-private-data
      gcs_project: your-project-id
      gcs_prefix: koinon/private-attachments
      request_timeout_seconds: 10
      max_object_bytes: 67108864
```

Use an existing bucket and Application Default Credentials, preferably workload identity. If your deployment uses `GOOGLE_APPLICATION_CREDENTIALS`, point it to the externally mounted credential/federation configuration file; never embed JSON credentials in source or the storage profile. `gcs_project` is optional for an existing bucket and does not grant bucket authority.

An optional `gcs_endpoint_url` selects an explicit HTTPS endpoint or loopback emulator. Only explicit loopback enables anonymous fixture credentials. Ambient `STORAGE_EMULATOR_HOST`/`API_ENDPOINT_OVERRIDE` values conflicting with the profile are rejected. Native structured `gs://bucket/prefix` roots remain supported. Object access and signed-URL signing credentials are distinct capabilities; no public fallback is provided.

## Environment and secret references

The shipped `koinon.main`/`koinon.serve` bootstrap loads `KOINON_CONFIG_FILE` and maps explicit product aliases onto the file configuration:

| Product alias family | Domain |
| --- | --- |
| `KOINON_DOCUMENT_STORAGE_*` | `koinon.storage.documents.*` |
| `KOINON_STRUCTURED_STORAGE_*` | `koinon.storage.structured.*` |
| `KOINON_ATTACHMENT_STORAGE_*` | `koinon.storage.attachments.*` |

Suffixes match the fields above: `BACKEND`, `ROOT`, `AZURE_ACCOUNT_URL`, `AZURE_CONTAINER`, `AZURE_PREFIX`, `GCS_BUCKET`, `GCS_PROJECT`, `GCS_PREFIX`, `GCS_ENDPOINT_URL`, `REQUEST_TIMEOUT_SECONDS` and `MAX_OBJECT_BYTES`. Document/private S3 additionally use their supported `S3_*` fields. Structured uses `PRESIGN_TTL_SECONDS`. The document original-retention alias is specifically `KOINON_DOCUMENT_STORE_ORIGINALS`.

Absent aliases preserve the configured values. A product alias overrides its matching file value. Native pyfly environment binding can override the final dotted property as well, such as `PYFLY_KOINON_STORAGE_ATTACHMENTS_ROOT`. Avoid conflicting naming families. Directly constructing `Config` does not run the product alias mapper; explicit `${ENV_VAR}` placeholders and native `PYFLY_` binding still apply. Retained `FLYCANON_OBJECT_STORE_*`/`FLYQUERY_OBJECT_STORE*` settings are lower-level inputs; explicit product-profile constructor values take precedence over their Pydantic environment fallback.

`${ENV_VAR}` references read externally supplied environment values; they are not a new secret-manager URI scheme. Prefer workload identity and secret-manager injection through the supported cloud SDK chain. Inspect only non-secret binding summaries during diagnosis; do not dump the full environment, database URLs, signed URLs or credentials.

## Limits, atomicity and lifecycle

| Boundary | Current behavior |
| --- | --- |
| Canonical library upload | One file per request; `koinon.knowledge.max_upload_bytes` defaults to 32 MiB. Request completion and any later indexing state remain distinct. |
| Shared Azure/GCS and private profile | `max_object_bytes`: 1–67,108,864, default 67,108,864; request timeout: integer 1–60 seconds, default 10. These are whole-object/socket budgets, not hard process deadlines. |
| Private chat policy | Separate `koinon.attachments` quotas: default file 20 MiB, image 8 MiB, thread 128 MiB/100 files, selected files at most 10, expiry 86,400 seconds. Parser budgets and worker enablement remain independent of the byte store. |
| Structured signing | Positive cloud URL lifetime of at most seven days; default profile TTL 86,400 seconds. Signing authority must be independently available. |
| Azure/GCS governed-query scratch | Registered pinned snapshots only, at most 128 tables and an aggregate scratch-byte budget; fresh private temporary files are cleaned after success/failure/cancellation. |

Private local writes use sibling staging, file/directory fsync and atomic replacement, then bounded digest verification. Retained document/structured local adapters use their native write paths; do not assume the private adapter's crash-atomic contract for all domains. Azure/GCS use conditional create and verify the exact size/SHA-256 on repeated keys. S3 adapter behavior differs; application version/lease/commit guards and unique registered keys remain necessary. A database transaction does not make a multi-store operation globally atomic.

The native context closes owned cloud clients and credentials after admitted operations drain; a borrowed client is not closed by its borrower. Shared threaded operations drain before propagating cancellation, including repeated cancellation. Socket timeouts do not bound credential discovery or guarantee a hard shutdown deadline. A completed object or abandoned multipart/resumable session may remain after a failed/cancelled caller. Keep provider lifecycle cleanup and temporary-file inspection separate from registered durable-object deletion.

Use least required object read/write/delete and bucket/container metadata/signing permissions for each configured namespace. Valid configuration and installed extras mean configured capability, not observed availability, replication, IAM, throughput or restore success. Complete owned provider and recovery qualification separately before relying on a deployment.

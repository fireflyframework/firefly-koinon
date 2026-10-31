<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Durable document and dataset intake

Use a durable file batch when a multi-file import needs a saved manifest, bounded uploads, per-file outcomes and restart reconciliation. A sequential loop around the single-file upload API remains a caller-owned loop. File batches use the existing native job queue and canonical document/Structured pipelines; they do not make all files one atomic transaction. Query batches are a separate capability and are not accepted as file modes.

The deployment must configure [durable private staging and its supported topology](../operations/durable-bulk.md), the appropriate native databases, readers and an authorized embedding connection. The capability response advertises `document` and `dataset` with `extract_only_v1`: extraction and admitted embeddings, without implicit authored naming or enrichment. Requesting a mode does not configure a provider. Bulk configuration and staging paths are deployment authority, not personal-token settings.

## Admit, upload, review and submit

1. Select an existing authorized workspace, its project and a collection or corpus in that project. Current `catalog:write` and `ingest:write` permissions are required. A PAT must also retain those scopes and applicable workspace/resource bounds; it cannot exceed the original subject's current role.
2. Persist an exact manifest and caller-owned admission key before creating a batch. Each item has a unique client ID, plain filename, mode, byte count and SHA-256. Admission reserves canonical identities before processing. Bounds are at most 100 files, 32 MiB per file and 256 MiB per batch, subject to smaller deployment limits and retained quotas.
3. Read the item page to match each client ID to its server item ID. Upload its exact original with a separate stable key. This is raw `application/octet-stream`, not multipart, JSON or base64. A changed length or digest conflicts. Receipt reads verify retained originals; they do not return private object keys or storage credentials.
4. After every original is staged, review the batch and submit with its current `revision` and a persisted submission key. HTTP202 means accepted, not indexed. An independently configured native bulk worker claims items; the general chat/job worker does not process this job kind.
5. Read batch and item pages for outcomes. Documents expose exact source-version/extraction IDs after success; datasets expose the reserved file-version and complete table IDs. Preserve historical IDs for audit and exact snapshot reads. A successful dataset has a receipt for every required table; a partial extraction or missing embedding does not become partial dataset success.

All mutation helpers require an explicit idempotency key. They send once and do not automatically retry failures, timeouts or unknown outcomes. Reusing the same key with a different manifest/action conflicts. Keys are bounded opaque identifiers, not secrets or payload containers.

The following functions only admit a manifest when invoked. Persist `key`, the exact bytes and the returned batch ID in your integration's durable job record. They do not upload, submit or poll automatically.

### Python

```python
import hashlib
from koinon_sdk import (
    BulkDestination, FileBatchCreate, FileBatchView, FileManifestItem, KoinonClient,
)

async def admit_dataset(
    client: KoinonClient, tenant: str, destination: BulkDestination,
    filename: str, content: bytes, key: str,
) -> FileBatchView:
    manifest = FileBatchCreate(destination=destination, items=[FileManifestItem(
        client_item_id="source-1", filename=filename, mode="dataset",
        size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
    )])
    return await client.create_file_batch(tenant, manifest, key)
```

Use `file_batch_items`, `upload_file_batch_item`, `file_batch_item_receipt` and `file_batch` to stage and inspect. `submit_file_batch`, `cancel_file_batch`, `reconcile_file_batch_item` and `reconcile_file_batch_original` take `BulkAction(expected_revision=current.revision)` plus the caller's stable key. `file_batches` and `file_batch_items` accept bounded `page` and `page_size`. Cancelling a Python await does not cancel a server batch; use the explicit cancellation operation and then inspect its result.

### TypeScript

```typescript
import {
  KoinonClient, type BulkDestination, type FileBatchView,
} from '@fireflyframework/koinon-sdk';

export async function admitDataset(
  client: KoinonClient, tenant: string, destination: BulkDestination,
  filename: string, content: Blob, key: string,
): Promise<FileBatchView> {
  const digest = await crypto.subtle.digest('SHA-256', await content.arrayBuffer());
  const sha256 = Array.from(new Uint8Array(digest),
    byte => byte.toString(16).padStart(2, '0')).join('');
  return client.fileBatches.create(tenant, {destination, items: [{
    client_item_id: 'source-1', filename, mode: 'dataset',
    size_bytes: content.size, sha256,
  }]}, key);
}
```

`fileBatches` exposes `capabilities`, `create`, `list`, `get`, `items`, `upload`, `receipt`, `submit`, `cancel`, `reconcile` and `recoverOriginal`. Pass an immutable `Blob` to `upload`; the helper preserves its raw bytes and sets the content type. Read methods and writes accept the usual `RequestOptions.signal`. An abort stops the client request; it does not prove a server mutation was cancelled. Keep the batch/item IDs and inspect the retained receipt before further action.

### Java21

```java
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class BulkExample {
  public static FileBatchView admitDataset(
      KoinonClient client, String tenant, BulkDestination destination,
      String filename, byte[] content, String key) throws Exception {
    String sha256 = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content));
    var item = new FileManifestItem("source-1", filename, AddKnowledgeMode.DATASET,
        content.length, sha256);
    return client.fileBatches(tenant).create(FileBatchCreate.empty()
        .withDestination(destination).withItems(List.of(item)), key);
  }
}
```

`client.fileBatches(tenant)` exposes the same eleven operations with synchronous and `Async` variants. `BulkFileUpload` defensively copies its bounded byte array and `upload` sends raw bytes. `FileBatchScope` carries the required workspace for capabilities; `FileBatchFilter` carries pagination. `BulkAction` uses an integer revision. Cancelling a future is client cancellation, not proof of server rollback. Keep explicit batch cancellation separate.

## Unknown outcomes and cancellation

Batch and item reads are read-only and recheck current authority before returning private metadata. Permission or token revocation can make an old batch unavailable. Knowing its ID does not grant access.

A completed native commit can be acknowledged from its immutable receipt without replaying the original or embeddings. A complete prepared dataset can publish its already-recorded table set under a current lease without parsing or model calls. An admitted or incomplete native effect remains `reconciling`; absence of a successful HTTP response is not permission to run it again.

`recoverOriginal` / `reconcile_file_batch_original` is a distinct explicit action for an interrupted staged upload. It requires the supported filesystem writer fence to prove that the original writer has stopped before verifying bytes and publishing a winner. It never replays original bytes. Do not use a new host's empty lock directory as that proof.

Cancellation prevents further claims and publication under a cancelled lease. A winning native commit remains successful and its originals and receipt remain retained. Mixed completed/cancelled files produce a partial batch outcome; cancellation is not a reset, deletion, refund or guarantee that no native preparation occurred. Reconcile an unknown result explicitly and preserve its evidence. Do not reset counters, delete failure records or replay old queued work during recovery.

A revision conflict requires reloading and reviewing the batch. Resource archive, changed native workspace binding or changed admitted embedding connection fails closed. A new import after review is a distinct admission; it does not overwrite an uncertain prior outcome.

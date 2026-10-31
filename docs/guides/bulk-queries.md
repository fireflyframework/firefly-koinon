<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Durable independent query batches

A query batch contains up to 20 independent natural-language questions against existing ready datasets in one workspace. It is separate from [file intake](bulk-intake.md), chat runs, saved conversations, and personal project memory. It accepts neither authored SQL nor a conversation ID. Questions do not share prior turns or another question's result.

Use the query-batch capability response for the selected tenant and workspace. `configured: true` requires current explicit validated provider bindings for structured embedding, grounding, generation, explanation, and the critic when the admitted organization policy enables refinement. `current_agent` bindings are not supported by this worker. The organization policy and connection identities are recorded at admission; changed bindings fail closed before execution or publication.

The original subject needs current `catalog:read` and `query:execute` authority over the workspace, each dataset and its canonical ancestors, and every referenced table. A PAT also needs those scopes and applicable saved workspace/resource bounds. Batch reads belong to the original subject and originating credential: switching from a PAT to a user session does not reveal that PAT's private batch. Questions and results are private, including page totals. Removed authority blocks later reads and model calls.

## Admit, inspect, and stop

Persist one admission key with the exact question manifest before sending it. Admission returns HTTP 201 and durable queued item IDs; it does not mean a model completed. An explicit worker claims the existing durable jobs. Inspect each item's status and typed result through the batch API. A queued, running, cancelled, or unresolved item can have `result: null`.

```python
from koinon_sdk import KoinonClient, QueryBatchCreate, QueryManifestItem

async def admit_queries(client: KoinonClient, tenant: str, workspace: str,
                        dataset: str, admission_key: str) -> str:
    batch = await client.create_query_batch(
        tenant,
        QueryBatchCreate(workspace_id=workspace, items=[
            QueryManifestItem(client_item_id="count", dataset_id=dataset,
                              question="How many records are present?")
        ]),
        admission_key,
    )
    return batch.id
```

```typescript
import {KoinonClient} from '@fireflyframework/koinon-sdk';

export async function admitQueries(client: KoinonClient, tenant: string,
  workspace: string, dataset: string, admissionKey: string): Promise<string> {
  const batch = await client.queryBatches.create(tenant, {
    workspace_id: workspace,
    items: [{client_item_id: 'count', dataset_id: dataset,
      question: 'How many records are present?'}],
  }, admissionKey);
  return batch.id;
}
```

```java
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.QueryBatchCreate;
import org.fireflyframework.koinon.sdk.model.QueryManifestItem;

final class QueryExample {
  static String admitQueries(KoinonClient client, String tenant, String workspace,
      String dataset, String admissionKey) {
    var request = QueryBatchCreate.empty().withWorkspaceId(workspace).withItems(List.of(
        new QueryManifestItem("count", dataset, "How many records are present?")));
    return client.queryBatches(tenant).create(request, admissionKey).id();
  }
}
```

List and item APIs use bounded `page`/`page_size` pagination. Result retrieval returns the saved native query ID, SQL, bounded preview, explanation, usage, effective policy, and immutable snapshot pins when recorded. A clarification or firewall rejection is an independent failed outcome; it is not a request to run another model automatically. The result receipt is limited to 1 MiB per item, previews to 100 rows, question text to 8,000 characters per item and 64 KiB UTF-8 per batch.

Cancellation requires the current batch revision and a separate persisted action key. It returns a small cancellation receipt; it does not return or erase private questions. Cancelling a queued item prevents execution. For an in-flight item, a native commit can win; cancellation never labels that committed result as undone. Check the resulting items after cancellation.

## Unknown outcomes remain unknown

A native operation marker is admitted before model work. Its committed receipt and native query row share one native transaction. If the process stops after admission without a complete native receipt, the item becomes `reconciling`. An expired lease, timeout, HTTP failure, or child exit is never evidence that the model did not run.

`reconcile_query_batch_item` / `queryBatches.reconcile` checks an existing native receipt. It can acknowledge an existing commit or close a proven never-started item; it cannot replay an admitted model operation. Preserve the batch, native operation marker, query rows, result objects and failure records. A new reviewed question admission is a distinct operation with a new key, not a retry disguised as recovery. Compatibility query routes do not expose batch-marked queries; their owner uses the private batch result route.

All SDK mutations send once. After a connection failure, retain the original key and inspect the batch before deciding on any new operation. A revision conflict requires reloading and reviewing current state. An abort signal or closing a client cancels the client request; use the durable cancellation operation to request that queued or running work stop.

## Deployment and qualification

Apply the additive primary query migration after the memory and dataset-reservation predecessors, and the structured query-operation migration after structured bulk receipts, before enabling these endpoints. Use the reviewed role-provisioning allowlist: query manifests, items and native operation receipts have no runtime `DELETE`; immutable reference rows permit only `SELECT,INSERT`. Migration and provider credentials are deployment authority, never personal-token fields.

`koinon.knowledge.bulk.query_worker_enabled` defaults to `false`. It is independent of the file-intake `worker_enabled` switch. An operator can run the dedicated native entry point `python -m koinon.knowledge.bulk_queries.worker`; the general job worker does not claim these jobs. The two bulk kinds share the configured global and per-tenant concurrency budget, lease bounds, owned-child kernel deadline and cleanup reserve. No scheduler, worker, grant or provider is enabled by submitting an API request.

Source and inert SDK/SQLite tests establish local behavior. They do not establish managed PostgreSQL concurrency, configured-provider model results, cloud placement, restore correctness or a production deployment. Those require separate qualification against the chosen deployment. File batches retain their [single-host durable POSIX staging contract](../operations/durable-bulk.md); choosing a cloud final object store does not extend that staging contract.

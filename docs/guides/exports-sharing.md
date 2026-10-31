# Export selected content and share reviewed messages

Exports and shares are available through the headless API and SDK. They use the caller's current organization and source permissions. A personal API token must include the narrow export, share or evidence scopes and their dependencies; its workspace and asset limits still apply.

## Review before creating

Request a short-lived review for the exact messages or stored query result you want to export. The response includes the selected text or stored schema, source references, omissions and a revision. Inspect that response before creating the export. Creation consumes the review once and rejects changed or expired content.

```typescript
const review = await client.exports.review(tenantId, {
  kind: 'conversation',
  thread_id: threadId,
  message_ids: selectedMessageIds,
  format: 'markdown',
  include_evidence: true,
});
```

After reviewing the returned selection, create and download the export:

```typescript
const exported = await client.exports.create(tenantId, {
  review_id: review.id,
  expected_revision: review.revision,
});
const file = await client.exports.download(tenantId, exported.id);
// file.blob contains authenticated bytes; file.filename is the safe download name.
```

Markdown and versioned JSON transcripts contain the selected messages. They exclude private attachment files and attachment metadata. A transcript can still contain the owner's reviewed answer text derived from a private attachment; this does not make that answer eligible for sharing.

Exports remain private to their owner. Downloading rechecks current source access and originating token validity. Cancellation prevents later downloads. Deployment limits bound active records, concurrent downloads, bytes and execution time. An expired stored result is not rerun automatically.

## Preserve the reviewed identity

New conversation reviews save `identity` alongside the selected messages. It records `product_name`, `assistant_name`, `branding_revision`, `branding_origin` and `branding_sha256`, the digest of the effective organization configuration. Image bytes, model instructions and credentials are excluded. The server obtains this identity through the caller's existing organization and resource permissions; the request cannot supply a replacement name.

The identity is included in the review revision. Renaming or resetting the organization afterward does not rename an existing share or export. Message and conversation revisions retain their original meaning. Creation still rejects changed content, changed source access, expired reviews and repeated confirmation.

`ExportReview`, `ShareReview` and `SharedConversation` expose the saved identity. Historical snapshots return `identity: null`; this means it was not recorded. Do not replace it with today's organization branding and call it historical identity. The exported transcript uses the original **koinon** label when identity is unknown. JSON transcripts preserve the machine role (`user` or `assistant`) and provide `display_name` separately. Markdown treats configured names as escaped text.

An embedded host's presentation override does not rewrite server snapshots. The server records the authorized organization identity, regardless of which host displayed the conversation. Legal attribution remains Firefly Software Foundation under Apache 2.0.

## Python and Java workflows

Use the authenticated clients from the [headless guide](headless.md). Pass actual organization, thread and message IDs from authorized responses. These helpers separate preview from confirmation: show the returned review and its omissions to the user before invoking the confirmation helper. They do not approve content automatically.

### Python

```python
from koinon_sdk import (
    ConversationExportInput, ExportCreate, ExportReview, KoinonClient,
    ShareCreate, ShareReview, ShareReviewInput,
)

async def review_export(client: KoinonClient, tenant: str, thread: str, messages: list[str]):
    return await client.review_export(tenant, ConversationExportInput(
        kind="conversation", thread_id=thread, message_ids=messages,
        format="markdown", include_evidence=True,
    ))

async def download_reviewed_export(client: KoinonClient, tenant: str, review: ExportReview):
    exported = await client.create_export(tenant, ExportCreate(
        review_id=review.id, expected_revision=review.revision,
    ))
    return await client.export_download(tenant, exported.id)

async def review_share(client: KoinonClient, tenant: str, thread: str, messages: list[str]):
    return await client.review_share(tenant, ShareReviewInput(thread_id=thread, message_ids=messages))

async def create_reviewed_share(client: KoinonClient, tenant: str, review: ShareReview):
    return await client.create_share(tenant, ShareCreate(
        review_id=review.id, expected_revision=review.revision, expires_in_hours=24,
    ))

async def read_shared_answer(client: KoinonClient, tenant: str, share_id: str):
    shared = await client.share(tenant, share_id)
    label = shared.identity.assistant_name if shared.identity is not None else "koinon"
    return label, shared
```

### Java

```java
import java.util.List;
import org.fireflyframework.koinon.sdk.BinaryResponse;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

final class ReviewedConversations {
    static ExportReview reviewExport(KoinonClient client, String tenant, String thread, List<String> messages) {
        return client.exports(tenant).review(new ConversationExportInput(
            thread, messages, ConversationExportInputKind.CONVERSATION,
            ConversationExportInputFormat.MARKDOWN, true));
    }

    static BinaryResponse downloadReviewedExport(KoinonClient client, String tenant, ExportReview review) {
        var exported = client.exports(tenant).create(new ExportCreate(review.id(), review.revision()));
        return client.exports(tenant).download(exported.id());
    }

    static ShareReview reviewShare(KoinonClient client, String tenant, String thread, List<String> messages) {
        return client.shares(tenant).review(new ShareReviewInput(thread, messages));
    }

    static Share createReviewedShare(KoinonClient client, String tenant, ShareReview review) {
        return client.shares(tenant).create(new ShareCreate(review.id(), review.revision(), 24,
            ShareRecipientPolicy.ORGANIZATION_CURRENT_ACL));
    }

    static String savedAssistantName(SharedConversation shared) {
        return shared.identity() == null ? "koinon" : shared.identity().assistantName();
    }
}
```

The Java SDK also supplies asynchronous variants such as `reviewAsync`, `createAsync` and `downloadAsync`. A successful HTTP response or typed deserialization does not establish model quality or complete historical provenance.

## Stored query data

Choose `kind: 'query_result'`, its canonical dataset ID and query ID, and one of `parquet`, `csv` or `jsonl`. The export reads the existing persisted Parquet artifact. It does not export only the displayed preview or rerun the query.

The stored execution may have been capped. Reviews report the observed stored row count and any recorded historical cap and truncation. Older executions may not record those fields or table snapshot pins; their completeness remains `unknown`. Unknown fields must not be treated as a complete SQL result or a complete dataset. An empty execution that stored no artifact or schema returns an actionable error instead of a fabricated file.

Parquet bytes remain unchanged. JSONL keeps decimal scale and represents integers outside JavaScript's safe range as strings. CSV offers two explicit modes:

| Mode | Behavior |
| --- | --- |
| `spreadsheet_safe` | Prefixes potentially executable **text cells** with an apostrophe, including formula prefixes and leading control characters. Numeric negatives remain numeric values. |
| `exact` | Preserves machine text values, including formula-like strings; select it when the consumer requires those original strings. |

CSV and JSONL require scalar columns; nested results remain available as Parquet. Conversions fail on limits rather than silently dropping rows. Data filenames end in `stored-result`, and download headers report stored rows, completeness, historical cap, truncation and snapshot-manifest observations. The SDK preserves these headers on `BinaryDownload.headers`.

## Authenticated shares

Use `client.shares.review(tenantId, {thread_id, message_ids})` to review the exact selected content. After reviewing it, create a share with its review ID and expected revision. Expiry defaults to 24 hours and is bounded to seven days; an originating or creator token can shorten it.

A share grants no additional permissions. Recipients must sign in and retain current access to every source. Owner membership, source ancestry, archival state and token validity are checked again when a recipient reads the share. Revocation disables subsequent reads. Sharing sends no email and creates no anonymous public link.

Private-derived answers are blocked from sharing. Incomplete historical source manifests are also blocked. These checks cannot be bypassed by deleting an attachment, choosing fewer visible citations or retrying through another token.

### TypeScript sharing

```typescript
import type {KoinonClient, ShareReview, SharedConversation} from '@fireflyframework/koinon-sdk';

export async function reviewShare(
  client: KoinonClient, tenant: string, thread: string, messages: string[],
) {
  return client.shares.review(tenant, {thread_id: thread, message_ids: messages});
}

export async function createReviewedShare(client: KoinonClient, tenant: string, review: ShareReview) {
  return client.shares.create(tenant, {
    review_id: review.id, expected_revision: review.revision, expires_in_hours: 24,
  });
}

export async function readShare(client: KoinonClient, tenant: string, shareId: string) {
  return client.shares.get(tenant, shareId);
}

export function savedAssistantName(shared: SharedConversation): string {
  return shared.identity?.assistant_name ?? 'koinon';
}
```

Only call `createReviewedShare` after the user accepts the preview. Read shares through the signed-in recipient's own client. A display fallback is a label, not evidence that an old identity was recorded.

## Inspect answer sources

`client.evidence.conversation(tenantId, {thread_id, message_ids})` returns the canonical source manifest for the selected messages. References distinguish the used revision or table snapshot from the source's current state. Available page, section and citation references identify the recorded location; changed or unverified provenance remains explicit.

Chunk processing offsets refer to the emitted chunk stream, including overlap. They are not coordinates in the original file and must not be used to highlight the original document. Original files remain separately authenticated downloads.

See the [API and SDK reference](../reference/sdk-api.md) for exact operation signatures and the [embedding guide](embedding.md) for optional Angular integration.

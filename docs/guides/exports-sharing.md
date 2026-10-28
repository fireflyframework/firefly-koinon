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

## Inspect answer sources

`client.evidence.conversation(tenantId, {thread_id, message_ids})` returns the canonical source manifest for the selected messages. References distinguish the used revision or table snapshot from the source's current state. Available page, section and citation references identify the recorded location; changed or unverified provenance remains explicit.

Chunk processing offsets refer to the emitted chunk stream, including overlap. They are not coordinates in the original file and must not be used to highlight the original document. Original files remain separately authenticated downloads.

See the [API and SDK reference](../reference/sdk-api.md) for exact operation signatures and the [embedding guide](embedding.md) for optional Angular integration.

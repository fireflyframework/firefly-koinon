<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java knowledge and files

Use the [Java quickstart](headless-java.md) to create a client. These helpers do not run on import or client construction. Call a write helper only after your application has selected and authorized the destination.

## Follow one asset through its lifecycle

This chapter starts with an existing workspace, creates a destination, uploads one source, and then reads its processing and historical identities. Use a small authorized document first. Repeat the intake decision for a real XLSX or another supported structured file only after you understand the returned receipt. The SDK does not turn arbitrary spreadsheet bytes into an admitted dataset by changing a filename.

You need `catalog:read` for browsing, `ingest:write` and its required catalog scopes for intake, `knowledge:search` for retrieval, and `query:execute` for SQL. Those scopes still intersect with current resource permissions. Use a workspace-bound integration for creating new assets. A token bounded to an existing asset is suitable for that asset's admitted operations, not for creating arbitrary siblings.

[The complete knowledge source](../examples/java/README.md) includes this chapter's helpers, reviewed replacement and append functions, and a read-only history entry point. Set `KOINON_DOCUMENT_ID` to a document selected from the authorized catalog before running that entry point. It prints source-version IDs and SHA256 values; it does not upload or replace anything automatically.

## Run the read-only chapter

Compile the complete classes using the Java source instructions before running this read-only command. `KOINON_SDK_CLASSPATH` contains the verified SDK and its declared Jackson dependencies. [Complete source and build instructions](../examples/java/README.md) include [the entry-point file](../examples/java/TutorialMain.java). This history command additionally needs an authorized `KOINON_DOCUMENT_ID` selected from the catalog. Keep credentials in the approved environment rather than adding them to these commands.

```sh
java -cp "classes:$KOINON_SDK_CLASSPATH" TutorialMain history
```

The result prints source-version IDs and SHA256 values from the first bounded page. No rows can mean no recorded versions in the authorized scope; preserve missing history instead of inventing a revision. If authorization fails, return to the setup chapter and inspect current context/scopes instead of broadening the request. The remaining helpers define the intended mutations, but this command does not invoke them.

## Catalog and source intake

First choose whether the caller is creating a new destination or reusing an existing one. The example creates a project and collection so the returned parent IDs are concrete. Record both IDs immediately; a later upload failure does not roll those writes back. In a repeatable integration, create the destination once, persist it, and reuse it rather than creating a new project for every file.

The upload's workspace, project, and parent identify the admitted destination. The filename is display metadata; the bytes are the source. Inspect the returned `source.id`, each `assets` entry, and optional `job_id`. Save that receipt before starting another file. If processing is asynchronous, inspect the identified job and resulting asset status before searching or querying the new content. An accepted request is not a completed extraction.


Catalog entries describe workspaces, projects, collections and knowledge assets. `catalog(tenant).list/get` reads them; `create/update/archive/restore/delete` manages supported catalog resources. An `ingest:write` token needs an admitted upload destination and the user's current write permission; `catalog:write` alone does not authorize ingestion. Asset-bound tokens cannot create arbitrary sibling assets. Use an authorized workspace-bound integration for new intake.

```java
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaIntake {
    public static UploadResponse upload(KoinonClient client, String tenant,
            String workspace, Path file, String mediaType, UploadMode mode) throws IOException {
        if (!Files.isRegularFile(file) || Files.size(file) == 0
                || Files.size(file) > 32L * 1024 * 1024) {
            throw new IllegalArgumentException("Choose a nonempty regular file up to 32 MiB");
        }
        var project = client.catalog(tenant).create(CatalogCreate.empty()
            .withKind("project").withName("Operations").withParentId(workspace));
        var collection = client.catalog(tenant).create(CatalogCreate.empty()
            .withKind("collection").withName("Policies").withParentId(project.id()));
        client.catalog(tenant).update(collection.id(), CatalogUpdate.empty()
            .withName("Approved policies"));
        return client.sources(tenant).upload(new SourceUpload(file, mediaType,
            workspace, project.id(), collection.id(), mode));
    }

    public static CatalogEntry archive(KoinonClient client, String tenant, String reviewedId) {
        return client.catalog(tenant).archive(reviewedId);
    }

    public static CatalogEntry restore(KoinonClient client, String tenant, String reviewedId) {
        return client.catalog(tenant).restore(reviewedId);
    }

    public static void deleteEmptyResource(KoinonClient client, String tenant, String reviewedId) {
        client.catalog(tenant).delete(reviewedId);
    }
}
```

Choose `UploadMode.DOCUMENT` or `UploadMode.DATASET` and a media type supported by the deployment. The 32 MiB check is a local example policy; the server applies its own limits and extractors. Keep source files stable until the request finishes. Save the canonical `UploadResponse` for each accepted upload and inspect `jobs(tenant)` when processing continues asynchronously.

Project creation, collection creation, rename and upload are separate writes. An upload failure does not undo an already created destination. For multiple files, use a bounded sequential loop or your own durable queue, record each accepted receipt immediately, and reconcile partial results. There is no atomic bulk import or automatic retry after an unknown outcome.

Archive, restore and deletion are separate explicit user choices. The server checks dependencies and retention rules: deletion can reject nonempty resources and immutable intake receipts. Curated knowledge changes require a reviewed intent rather than direct catalog mutation. Do not turn a permission or retention error into a recursive delete loop.

## Import an XLSX as a dataset

Select `dataset` intake for a supported workbook. Keep the original filename and bytes, and choose the same authorized destination deliberately. Call `JavaIntake.upload` with `UploadMode.DATASET` and the supported workbook media type. The destination IDs have the same meaning as the document example.

After processing, call `datasets(tenant).schema` with the **returned dataset asset ID**. Inspect the returned tables and columns before writing SQL. A workbook can produce multiple tables; the source catalog ID, dataset asset ID, table ID, catalog file-version ID, and immutable table snapshot ID serve different purposes. Do not assume the upload source is itself the SQL dataset or manufacture table IDs from sheet labels.

Append another supported file with `datasets(tenant).appendFile` only after the person has selected the existing dataset and the exact file. Generate and durably retain one idempotency key for that intended append before sending it. Keep that key bound to the same bytes and destination. Save the returned file-version and table IDs. A pending or unknown result needs reconciliation; changing the key does not turn it into a new safe attempt.

Replacing a table requires its current snapshot precondition, while appending adds a file. Replacing a document requires its original digest and, when supplied, its matching source-version/extraction pair. These are different user decisions. Use the complete source's append and replacement helpers rather than using catalog metadata updates as a content upload.

## Search and query within the admitted scope

```java
import java.util.List;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaKnowledgeReads {
    public static SearchResponse passages(KoinonClient client, String tenant,
            String workspace, List<String> selectedAssets, String question) {
        return client.knowledge(tenant).search(SearchRequest.empty()
            .withWorkspaceId(workspace).withAssetIds(selectedAssets)
            .withQuestion(question).withLimit(10L).withAnswer(false));
    }

    public static QueryResponse query(KoinonClient client, String tenant,
            String datasetId, String question, String reviewedReadOnlySql) {
        return client.knowledge(tenant).query(QueryRequest.empty()
            .withDatasetId(datasetId).withQuestion(question).withSql(reviewedReadOnlySql));
    }
}
```

Search requires `knowledge:search`; SQL requires `query:execute`, the current authorized dataset and the server's read-only query policy. Select a workspace and supported asset IDs deliberately; an empty selection must not be interpreted by your application as a new permission grant. `answer=false` requests retrieval without a generated answer, but retrieval can still use the deployment's configured embedding/search providers. Direct SQL remains subject to server admission and validation; a client-supplied SQL string cannot override them. Preserve typed exact values and returned truncation/metadata rather than assuming every result is complete.

Generation can invoke configured models. Read [Knowledge runtime](../concepts/knowledge-runtime.md) before choosing RAG/RLM or embedding behavior, and [Conversations and reviewed actions](java-conversations.md) for durable answers and their audit.

## Read immutable history and provenance

| Resource | Typed Java methods | Keep these identifiers |
| --- | --- | --- |
| Document originals | `documents(tenant).versions/version/versionOriginal/downloadVersionOriginal` | Document ID and source-version ID; original SHA256 |
| Document extractions | `documents(tenant).extractions/parts/part` | Source-version, extraction and part IDs; recorded part hashes |
| Current table schema | `datasets(tenant).schema` | Dataset, table and current snapshot IDs |
| Table history | `datasets(tenant).tableSnapshots` | Selected immutable snapshot ID and predecessor ID |
| Table provenance | `datasets(tenant).tableProvenance` | Exact snapshot ID, source artifact, parser/reader identity and transform steps when recorded |
| Coordinates | `tableCoordinates/tableCoordinateCells/tableCoordinateRows/tableCoordinateColumns` | The same selected snapshot ID; bounded row/cell/column selection |
| Asset relationships | `knowledge(tenant).lineage` | Catalog asset IDs and returned authorized edges |

```java
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaHistory {
    public static DocumentVersionPage documentVersions(KoinonClient client,
            String tenant, String documentId, int page) {
        return client.documents(tenant).versions(documentId,
            DocumentHistoryFilter.empty().withPage(page).withPageSize(25));
    }

    public static TableProvenance tableProvenance(KoinonClient client, String tenant,
            String datasetId, String tableId, String selectedSnapshotId) {
        return client.datasets(tenant).tableProvenance(datasetId, tableId,
            TableProvenanceFilter.empty().withSnapshotId(selectedSnapshotId));
    }

    public static Lineage lineage(KoinonClient client, String tenant, String assetId) {
        return client.knowledge(tenant).lineage(LineageFilter.empty().withAssetId(assetId));
    }
}
```

Pass the selected snapshot explicitly instead of substituting the current head when opening historical coordinates. A missing historical source, original connection, coordinate or reader hash is not reconstructed from today's configuration. Preserve null and `not_recorded` states. Provenance can describe an imported immutable snapshot; it does not establish a live read from the original database. History pages retain their own totals and page metadata; follow those fields rather than assuming all history fits in one response.

## Connect retrieval, SQL and lineage

Start retrieval with a question and the chosen workspace; keep `answer=false` when you want matching passages without a generated answer. Check hit references and scores before asking for generation. Retrieval can still use a configured embedding service, so an error here may be a configuration/provider failure rather than an empty result. Do not remove scope filters to hide that failure.

For structured data, inspect the schema, choose one actual dataset, and submit bounded read-only SQL using its real table and column names. Use a small row limit appropriate to your task. Inspect `execution_status`, truncation and immutable snapshot pins before displaying the result as complete. An authorization or SQL-firewall rejection must be corrected explicitly; the SDK does not run arbitrary SQL against the original upstream database.

Call `knowledge(tenant).lineage` for the selected catalog asset to read its currently authorized relationships. For document evidence, follow source version, extraction and part IDs. For table evidence, select a recorded snapshot before reading provenance or coordinates. A relationship edge explains a recorded connection; it is not proof that every cell has a known origin. Leave unavailable or unrecorded identities unknown.

## Replace content with current revisions

A document byte digest and an extraction revision identify different things. Read the current original version and chunk head, show the content-change effects to the user, and bind both when replacing or reingesting. An identical original digest does not prove that the extraction is unchanged.

```java
import java.nio.file.Path;
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.RequestOptions;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaContentChanges {
    public static ContentUpdate replaceDocument(KoinonClient client, String tenant,
            String documentId, DocumentVersion original, DocumentChunks head,
            Path replacement, String mediaType, boolean reviewedChunkInvalidation) {
        if (!reviewedChunkInvalidation) {
            throw new IllegalArgumentException("Review chunk invalidation before replacing content");
        }
        if (!original.sourceVersionId().equals(head.sourceVersionId())) {
            throw new IllegalArgumentException("Read a matching original version and extraction head");
        }
        var options = RequestOptions.defaults()
            .documentRevision(original.sourceVersionId(), head.extractionId());
        return client.documents(tenant).replace(documentId,
            new DocumentReplacement(replacement, mediaType, true), original.sha256(), options);
    }

    public static ContentUpdate reingestDocument(KoinonClient client, String tenant,
            String documentId, DocumentVersion original, DocumentChunks head,
            boolean reviewedChunkInvalidation) {
        if (!reviewedChunkInvalidation || !original.sourceVersionId().equals(head.sourceVersionId())) {
            throw new IllegalArgumentException("Review the current matching document revision");
        }
        return client.documents(tenant).reingest(documentId,
            DocumentReingestInput.empty().withAcknowledgeChunkInvalidation(true),
            original.sha256(), RequestOptions.defaults()
                .documentRevision(original.sourceVersionId(), head.extractionId()));
    }

    public static ContentUpdate replaceTable(KoinonClient client, String tenant,
            String datasetId, SchemaTable current, Path replacement, String mediaType) {
        return client.datasets(tenant).replaceTable(datasetId, current.id(),
            new TableReplacement(replacement, mediaType), current.snapshotId());
    }

    public static ContentUpdate reingestTable(KoinonClient client, String tenant,
            String datasetId, SchemaTable current) {
        return client.datasets(tenant).reingestTable(datasetId, current.id(),
            TableReingestInput.empty(), current.snapshotId());
    }

    public static DatasetFileAppendResult append(KoinonClient client, String tenant,
            String datasetId, Path file, String mediaType, String stableRequestId) {
        return client.datasets(tenant).appendFile(datasetId,
            new DatasetFileUpload(file, mediaType), stableRequestId);
    }
}
```

`replace` and `reingest` send the expected original SHA256 as `If-Match`; `documentRevision` adds the exact source-version/extraction pair. Table changes use the current `SchemaTable.snapshotId()` from `datasets(tenant).schema(datasetId)` as `If-Match`. After a conflict, read current state and review the new effects; do not silently update the precondition and replay the write. Inspect the returned `ContentUpdate.effects()` and canonical identifiers rather than assuming old chunks or snapshots are still current.

Retain `ContentUpdate.version()` when the response supplies a catalog version entry. Catalog asset/version IDs, document source-version/extraction IDs and structured snapshot IDs describe different identities; do not substitute one for another. A catalog rename changes metadata rather than proving new source bytes or a new extraction. Use `catalog(tenant).get` for the catalog entry and the native history methods below for its content history.

`appendFile` adds one file and its parsed tables to an existing dataset. Persist its caller-supplied stable request key and `DatasetFileAppendResult` before proceeding. The receipt includes canonical `fileVersionId()` and `tableIds()`. The same key and identical payload can return the retained receipt after current authorization; a changed payload conflicts. Pending or failed intake can block query/schema until reconciliation while previous files and snapshots remain retained. Native sections commit independently. This is neither atomic bulk intake nor a client recovery command; never invent a new key to bypass an unresolved outcome.

## Decide what to do after a content change

Present the current digest/snapshot and the effects of replacement before asking for confirmation. The reviewed replacement helper takes the already reviewed identities; it does not silently read a newer revision and overwrite it. A conflict means the user must inspect the new head and make another decision. Keep invalidation acknowledgment false until the user understands the affected chunks or dependencies.

After success, retain `ContentUpdate.asset`, `version`, and `effects`. Reload the current catalog and inspect its new native history before using old chunk or snapshot IDs as current. Historical IDs remain historical even when the asset name is unchanged. If a write times out, reconcile the saved operation and current state first; a missing HTTP response does not prove that no change occurred.

## Curated knowledge and reviewed commits

`knowledgeItems(tenant).list/get/version` reads curated items and exact versions. Content changes use `knowledgeIntents(tenant).preview/get/confirm/cancel`. The intent actions support draft/published creation and update, plus explicit `PUBLISH_DRAFT` for an existing draft. There is no general curated-delete operation; do not emulate one with raw catalog deletion or invented endpoints.

```java
import org.fireflyframework.koinon.sdk.KoinonClient;
import org.fireflyframework.koinon.sdk.model.*;

public final class JavaCuratedKnowledge {
    public static KnowledgeIntent previewDraft(KoinonClient client, String tenant,
            String destinationId, KnowledgeContent content) {
        return client.knowledgeIntents(tenant).preview(KnowledgeIntentInput.empty()
            .withAction(ExternalReviewInputAction.CREATE_DRAFT)
            .withDestinationId(destinationId).withContent(content)
            .withOrigin(new UserStatementOrigin(UserStatementEvidenceKind.USER_STATEMENT)));
    }

    public static KnowledgeCommitOutcome confirmReviewed(KoinonClient client, String tenant,
            String intentId, long reviewedRevision, String reviewedDigest,
            String stableRequestId, boolean personConfirmed) {
        if (!personConfirmed) throw new IllegalArgumentException("Explicit confirmation required");
        return client.knowledgeIntents(tenant).confirm(intentId, KnowledgeConfirmation.empty()
            .withConfirm(true).withExpectedRevision(reviewedRevision)
            .withAuthorizationDigest(reviewedDigest), stableRequestId);
    }
}
```

Display the server's `before`, `after`, destination, evidence, expiry and current revision before asking a person to confirm. Pass the exact reviewed revision and authorization digest to the separate helper. To update, preview with `UPDATE_DRAFT` or `UPDATE_PUBLISHED` and the existing `targetItemId` and `expectedVersion`; use `PUBLISH_DRAFT` to explicitly publish the selected draft. Keep committed and pending outcomes distinct and reconcile with the saved intent/receipt. Never report pending as committed or have a stream handler confirm an intent automatically.

A user-statement origin means exactly that; it is not an external-source citation. Server-issued MCP read receipts and external files use [external knowledge reviews](mcp-knowledge-management.md), with their own component-bound nonce and exact revision/digest rules. The Java methods do not manufacture receipt IDs, a human confirmation, provider access or provenance that the server did not observe.

When a conversation-origin intent reports `remembered_context_present`, show the remembered-context explanation alongside the exact intent preview and obtain a separate decision. Only an explicit approval permits `include_remembered_context=true` on `KnowledgeConfirmation` (Java: `withIncludeRememberedContext(true)`). The examples above leave that consent disabled. Evidence marked `basis: remembered_context` remains attributed to its recorded historical source rather than being presented as new retrieval. See [conversation memory](conversation-memory.md#share-or-publish-an-answer-that-used-memory) for the complete behavior.

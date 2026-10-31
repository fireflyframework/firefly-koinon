<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
# Java knowledge and files

Use the [Java quickstart](headless-java.md) to create a client. These helpers do not run on import or client construction. Call a write helper only after your application has selected and authorized the destination.

## Catalog and source intake

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

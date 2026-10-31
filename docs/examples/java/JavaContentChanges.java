// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
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

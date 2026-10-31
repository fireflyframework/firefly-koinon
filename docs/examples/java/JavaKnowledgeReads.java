// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
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

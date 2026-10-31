// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
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

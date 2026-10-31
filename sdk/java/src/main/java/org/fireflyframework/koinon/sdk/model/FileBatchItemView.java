// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical FileBatchItemView contract. */
public record FileBatchItemView(
    @JsonProperty("id") String id,
    @JsonProperty("client_item_id") String clientItemId,
    @JsonProperty("filename") String filename,
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("size_bytes") Long sizeBytes,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("status") FileBatchItemViewStatus status,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("job_id") String jobId,
    @JsonProperty("file_version_id") String fileVersionId,
    @JsonProperty("table_ids") List<String> tableIds,
    @JsonProperty("source_version_id") String sourceVersionId,
    @JsonProperty("extraction_id") String extractionId,
    @JsonProperty("error_code") String errorCode
) {
    public FileBatchItemView {
        tableIds=tableIds==null?null:List.copyOf(tableIds);
    }

}

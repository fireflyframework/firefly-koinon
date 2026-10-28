// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DatasetFileAppendResult contract. */
public record DatasetFileAppendResult(
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("file_version_id") String fileVersionId,
    @JsonProperty("filename") String filename,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("byte_size") Long byteSize,
    @JsonProperty("table_ids") List<String> tableIds,
    @JsonProperty("status") DatasetFileAppendResultStatus status
) {
    public DatasetFileAppendResult {
        tableIds=tableIds==null?null:List.copyOf(tableIds);
    }

}

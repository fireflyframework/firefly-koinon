// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical TableSnapshotSummary contract. */
public record TableSnapshotSummary(
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("table_id") String tableId,
    @JsonProperty("native_dataset_id") String nativeDatasetId,
    @JsonProperty("native_table_id") String nativeTableId,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("status") AnswerAuditProvenanceStatus status,
    @JsonProperty("snapshot_status") TableProvenanceSnapshotStatus snapshotStatus,
    @JsonProperty("level") TableProvenanceLevel level,
    @JsonProperty("operation") TableProvenanceOperation operation,
    @JsonProperty("predecessor_snapshot_id") String predecessorSnapshotId,
    @JsonProperty("artifact") ProvenanceArtifact artifact,
    @JsonProperty("sheet_or_json_path") String sheetOrJsonPath,
    @JsonProperty("table_label") String tableLabel,
    @JsonProperty("parquet_sha256") String parquetSha256,
    @JsonProperty("parquet_byte_size") Long parquetByteSize,
    @JsonProperty("schema_sha256") String schemaSha256,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("actor") String actor,
    @JsonProperty("recorded_at") Instant recordedAt
) {

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical TableCoordinateManifest contract. */
public record TableCoordinateManifest(
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("table_id") String tableId,
    @JsonProperty("native_dataset_id") String nativeDatasetId,
    @JsonProperty("native_table_id") String nativeTableId,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("status") TableCoordinateManifestStatus status,
    @JsonProperty("index_base") Integer indexBase,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("column_count") Long columnCount,
    @JsonProperty("artifact_id") String artifactId,
    @JsonProperty("run_id") String runId,
    @JsonProperty("input_sha256") String inputSha256,
    @JsonProperty("mapping_sha256") String mappingSha256,
    @JsonProperty("source_format") String sourceFormat,
    @JsonProperty("source_variant") String sourceVariant,
    @JsonProperty("row_kind") TableCoordinateManifestRowKind rowKind,
    @JsonProperty("source_sheet") String sourceSheet,
    @JsonProperty("source_path") List<JsonNode> sourcePath,
    @JsonProperty("parser_decisions") List<CoordinateParserDecision> parserDecisions,
    @JsonProperty("dependencies") List<CoordinateDependency> dependencies,
    @JsonProperty("reason_code") String reasonCode,
    @JsonProperty("rejected_source_rows") List<Long> rejectedSourceRows
) {
    public TableCoordinateManifest {
        sourcePath=ModelValues.jsonList(sourcePath);
        parserDecisions=parserDecisions==null?null:List.copyOf(parserDecisions);
        dependencies=dependencies==null?null:List.copyOf(dependencies);
        rejectedSourceRows=rejectedSourceRows==null?null:List.copyOf(rejectedSourceRows);
    }
    @Override public List<JsonNode> sourcePath(){return ModelValues.jsonList(sourcePath);}
}

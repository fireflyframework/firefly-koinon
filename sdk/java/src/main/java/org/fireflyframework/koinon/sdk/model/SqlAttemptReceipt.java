// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;



/** Typed canonical SqlAttemptReceipt contract. */
public record SqlAttemptReceipt(
    @JsonProperty("result_id") String resultId,
    @JsonProperty("generation_id") String generationId,
    @JsonProperty("ordinal") Integer ordinal,
    @JsonProperty("stage") String stage,
    @JsonProperty("statement_sha256") String statementSha256,
    @JsonProperty("statement") String statement,
    @JsonProperty("classification") String classification,
    @JsonProperty("outcome") String outcome,
    @JsonProperty("executed") Boolean executed,
    @JsonProperty("snapshot_pins") Map<String,String> snapshotPins,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("truncated") Boolean truncated,
    @JsonProperty("reason_code") String reasonCode,
    @JsonProperty("engine") String engine,
    @JsonProperty("database") String database,
    @JsonProperty("catalog") String catalog,
    @JsonProperty("schema") String schema,
    @JsonProperty("execution_kind") SqlAttemptReceiptExecutionKind executionKind,
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("native_dataset_id") String nativeDatasetId,
    @JsonProperty("tables") List<NativeTableSnapshot> tables
) {
    public SqlAttemptReceipt {
        snapshotPins=snapshotPins==null?null:Map.copyOf(snapshotPins);
        tables=tables==null?null:List.copyOf(tables);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ReplaceTable contract. */
public record ReplaceTable(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("action") ReplaceTableAction action,
    @JsonProperty("dataset_id") String datasetId,
    @JsonProperty("table_id") String tableId,
    @JsonProperty("expected_snapshot_id") String expectedSnapshotId
) implements AttachmentPromotionInput {

    public static ReplaceTable empty(){return new ReplaceTable(null,null,null,null,null);}
    public ReplaceTable withExpectedRevision(Long value){return new ReplaceTable(value,action,datasetId,tableId,expectedSnapshotId);}
    public ReplaceTable withAction(ReplaceTableAction value){return new ReplaceTable(expectedRevision,value,datasetId,tableId,expectedSnapshotId);}
    public ReplaceTable withDatasetId(String value){return new ReplaceTable(expectedRevision,action,value,tableId,expectedSnapshotId);}
    public ReplaceTable withTableId(String value){return new ReplaceTable(expectedRevision,action,datasetId,value,expectedSnapshotId);}
    public ReplaceTable withExpectedSnapshotId(String value){return new ReplaceTable(expectedRevision,action,datasetId,tableId,value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CoordinateCellRequest contract. */
public record CoordinateCellRequest(
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("cells") List<CoordinateCellPosition> cells
) {
    public CoordinateCellRequest {
        cells=cells==null?null:List.copyOf(cells);
    }

    public static CoordinateCellRequest empty(){return new CoordinateCellRequest(null,null);}
    public CoordinateCellRequest withSnapshotId(String value){return new CoordinateCellRequest(value,cells);}
    public CoordinateCellRequest withCells(List<CoordinateCellPosition> value){return new CoordinateCellRequest(snapshotId,value);}
}

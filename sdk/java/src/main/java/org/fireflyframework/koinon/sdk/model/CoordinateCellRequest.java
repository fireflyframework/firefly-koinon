// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical CoordinateCellRequest contract. */
public record CoordinateCellRequest(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("cells") List<CoordinateCellPosition> cells
) {
    public CoordinateCellRequest {
        cells=cells==null?null:List.copyOf(cells);
    }

    public static CoordinateCellRequest empty(){return new CoordinateCellRequest(null,null,null);}
    public CoordinateCellRequest withReaderSourceConnections(List<ReaderSourceSelection> value){return new CoordinateCellRequest(JsonField.of(value),snapshotId,cells);}
    public CoordinateCellRequest clearReaderSourceConnections(){return new CoordinateCellRequest(JsonField.clear(),snapshotId,cells);}
    public CoordinateCellRequest omitReaderSourceConnections(){return new CoordinateCellRequest(null,snapshotId,cells);}
    public CoordinateCellRequest withSnapshotId(String value){return new CoordinateCellRequest(readerSourceConnections,value,cells);}
    public CoordinateCellRequest withCells(List<CoordinateCellPosition> value){return new CoordinateCellRequest(readerSourceConnections,snapshotId,value);}
}

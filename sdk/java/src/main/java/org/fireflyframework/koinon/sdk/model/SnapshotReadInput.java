// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SnapshotReadInput contract. */
public record SnapshotReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("snapshot_id") String snapshotId
) {

    public static SnapshotReadInput empty(){return new SnapshotReadInput(null,null);}
    public SnapshotReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new SnapshotReadInput(JsonField.of(value),snapshotId);}
    public SnapshotReadInput clearReaderSourceConnections(){return new SnapshotReadInput(JsonField.clear(),snapshotId);}
    public SnapshotReadInput omitReaderSourceConnections(){return new SnapshotReadInput(null,snapshotId);}
    public SnapshotReadInput withSnapshotId(String value){return new SnapshotReadInput(readerSourceConnections,value);}
}

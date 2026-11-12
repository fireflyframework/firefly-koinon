// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SnapshotPageReadInput contract. */
public record SnapshotPageReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("page") Integer page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("snapshot_id") String snapshotId
) {

    public static SnapshotPageReadInput empty(){return new SnapshotPageReadInput(null,null,null,null);}
    public SnapshotPageReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new SnapshotPageReadInput(JsonField.of(value),page,pageSize,snapshotId);}
    public SnapshotPageReadInput clearReaderSourceConnections(){return new SnapshotPageReadInput(JsonField.clear(),page,pageSize,snapshotId);}
    public SnapshotPageReadInput omitReaderSourceConnections(){return new SnapshotPageReadInput(null,page,pageSize,snapshotId);}
    public SnapshotPageReadInput withPage(Integer value){return new SnapshotPageReadInput(readerSourceConnections,value,pageSize,snapshotId);}
    public SnapshotPageReadInput withPageSize(Integer value){return new SnapshotPageReadInput(readerSourceConnections,page,value,snapshotId);}
    public SnapshotPageReadInput withSnapshotId(String value){return new SnapshotPageReadInput(readerSourceConnections,page,pageSize,value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SnapshotHistoryReadInput contract. */
public record SnapshotHistoryReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("cursor") JsonField<String> cursor,
    @JsonProperty("page_size") Integer pageSize
) {

    public static SnapshotHistoryReadInput empty(){return new SnapshotHistoryReadInput(null,null,null);}
    public SnapshotHistoryReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new SnapshotHistoryReadInput(JsonField.of(value),cursor,pageSize);}
    public SnapshotHistoryReadInput clearReaderSourceConnections(){return new SnapshotHistoryReadInput(JsonField.clear(),cursor,pageSize);}
    public SnapshotHistoryReadInput omitReaderSourceConnections(){return new SnapshotHistoryReadInput(null,cursor,pageSize);}
    public SnapshotHistoryReadInput withCursor(String value){return new SnapshotHistoryReadInput(readerSourceConnections,JsonField.of(value),pageSize);}
    public SnapshotHistoryReadInput clearCursor(){return new SnapshotHistoryReadInput(readerSourceConnections,JsonField.clear(),pageSize);}
    public SnapshotHistoryReadInput omitCursor(){return new SnapshotHistoryReadInput(readerSourceConnections,null,pageSize);}
    public SnapshotHistoryReadInput withPageSize(Integer value){return new SnapshotHistoryReadInput(readerSourceConnections,cursor,value);}
}

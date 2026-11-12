// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ReaderPageInput contract. */
public record ReaderPageInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("page") Integer page,
    @JsonProperty("page_size") Integer pageSize
) {

    public static ReaderPageInput empty(){return new ReaderPageInput(null,null,null);}
    public ReaderPageInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new ReaderPageInput(JsonField.of(value),page,pageSize);}
    public ReaderPageInput clearReaderSourceConnections(){return new ReaderPageInput(JsonField.clear(),page,pageSize);}
    public ReaderPageInput omitReaderSourceConnections(){return new ReaderPageInput(null,page,pageSize);}
    public ReaderPageInput withPage(Integer value){return new ReaderPageInput(readerSourceConnections,value,pageSize);}
    public ReaderPageInput withPageSize(Integer value){return new ReaderPageInput(readerSourceConnections,page,value);}
}

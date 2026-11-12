// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ExportBrowseInput contract. */
public record ExportBrowseInput(
    @JsonProperty("q") String q,
    @JsonProperty("status") ExportBrowseInputStatus status,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("cursor") JsonField<String> cursor,
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections
) {

    public static ExportBrowseInput empty(){return new ExportBrowseInput(null,null,null,null,null);}
    public ExportBrowseInput withQ(String value){return new ExportBrowseInput(value,status,pageSize,cursor,readerSourceConnections);}
    public ExportBrowseInput withStatus(ExportBrowseInputStatus value){return new ExportBrowseInput(q,value,pageSize,cursor,readerSourceConnections);}
    public ExportBrowseInput withPageSize(Integer value){return new ExportBrowseInput(q,status,value,cursor,readerSourceConnections);}
    public ExportBrowseInput withCursor(String value){return new ExportBrowseInput(q,status,pageSize,JsonField.of(value),readerSourceConnections);}
    public ExportBrowseInput clearCursor(){return new ExportBrowseInput(q,status,pageSize,JsonField.clear(),readerSourceConnections);}
    public ExportBrowseInput omitCursor(){return new ExportBrowseInput(q,status,pageSize,null,readerSourceConnections);}
    public ExportBrowseInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new ExportBrowseInput(q,status,pageSize,cursor,JsonField.of(value));}
    public ExportBrowseInput clearReaderSourceConnections(){return new ExportBrowseInput(q,status,pageSize,cursor,JsonField.clear());}
    public ExportBrowseInput omitReaderSourceConnections(){return new ExportBrowseInput(q,status,pageSize,cursor,null);}
}

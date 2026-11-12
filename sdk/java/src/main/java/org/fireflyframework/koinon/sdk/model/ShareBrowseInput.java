// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ShareBrowseInput contract. */
public record ShareBrowseInput(
    @JsonProperty("q") String q,
    @JsonProperty("status") ShareBrowseInputStatus status,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("cursor") JsonField<String> cursor,
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections
) {

    public static ShareBrowseInput empty(){return new ShareBrowseInput(null,null,null,null,null);}
    public ShareBrowseInput withQ(String value){return new ShareBrowseInput(value,status,pageSize,cursor,readerSourceConnections);}
    public ShareBrowseInput withStatus(ShareBrowseInputStatus value){return new ShareBrowseInput(q,value,pageSize,cursor,readerSourceConnections);}
    public ShareBrowseInput withPageSize(Integer value){return new ShareBrowseInput(q,status,value,cursor,readerSourceConnections);}
    public ShareBrowseInput withCursor(String value){return new ShareBrowseInput(q,status,pageSize,JsonField.of(value),readerSourceConnections);}
    public ShareBrowseInput clearCursor(){return new ShareBrowseInput(q,status,pageSize,JsonField.clear(),readerSourceConnections);}
    public ShareBrowseInput omitCursor(){return new ShareBrowseInput(q,status,pageSize,null,readerSourceConnections);}
    public ShareBrowseInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new ShareBrowseInput(q,status,pageSize,cursor,JsonField.of(value));}
    public ShareBrowseInput clearReaderSourceConnections(){return new ShareBrowseInput(q,status,pageSize,cursor,JsonField.clear());}
    public ShareBrowseInput omitReaderSourceConnections(){return new ShareBrowseInput(q,status,pageSize,cursor,null);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical MessageBrowseInput contract. */
public record MessageBrowseInput(
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("cursor") JsonField<String> cursor,
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections
) {

    public static MessageBrowseInput empty(){return new MessageBrowseInput(null,null,null);}
    public MessageBrowseInput withPageSize(Integer value){return new MessageBrowseInput(value,cursor,readerSourceConnections);}
    public MessageBrowseInput withCursor(String value){return new MessageBrowseInput(pageSize,JsonField.of(value),readerSourceConnections);}
    public MessageBrowseInput clearCursor(){return new MessageBrowseInput(pageSize,JsonField.clear(),readerSourceConnections);}
    public MessageBrowseInput omitCursor(){return new MessageBrowseInput(pageSize,null,readerSourceConnections);}
    public MessageBrowseInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new MessageBrowseInput(pageSize,cursor,JsonField.of(value));}
    public MessageBrowseInput clearReaderSourceConnections(){return new MessageBrowseInput(pageSize,cursor,JsonField.clear());}
    public MessageBrowseInput omitReaderSourceConnections(){return new MessageBrowseInput(pageSize,cursor,null);}
}

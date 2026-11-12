// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DocumentChunksReadInput contract. */
public record DocumentChunksReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("offset") Long offset,
    @JsonProperty("limit") Integer limit,
    @JsonProperty("page") JsonField<Long> page,
    @JsonProperty("section") JsonField<String> section,
    @JsonProperty("q") JsonField<String> q
) {

    public static DocumentChunksReadInput empty(){return new DocumentChunksReadInput(null,null,null,null,null,null);}
    public DocumentChunksReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new DocumentChunksReadInput(JsonField.of(value),offset,limit,page,section,q);}
    public DocumentChunksReadInput clearReaderSourceConnections(){return new DocumentChunksReadInput(JsonField.clear(),offset,limit,page,section,q);}
    public DocumentChunksReadInput omitReaderSourceConnections(){return new DocumentChunksReadInput(null,offset,limit,page,section,q);}
    public DocumentChunksReadInput withOffset(Long value){return new DocumentChunksReadInput(readerSourceConnections,value,limit,page,section,q);}
    public DocumentChunksReadInput withLimit(Integer value){return new DocumentChunksReadInput(readerSourceConnections,offset,value,page,section,q);}
    public DocumentChunksReadInput withPage(Long value){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,JsonField.of(value),section,q);}
    public DocumentChunksReadInput clearPage(){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,JsonField.clear(),section,q);}
    public DocumentChunksReadInput omitPage(){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,null,section,q);}
    public DocumentChunksReadInput withSection(String value){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,page,JsonField.of(value),q);}
    public DocumentChunksReadInput clearSection(){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,page,JsonField.clear(),q);}
    public DocumentChunksReadInput omitSection(){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,page,null,q);}
    public DocumentChunksReadInput withQ(String value){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,page,section,JsonField.of(value));}
    public DocumentChunksReadInput clearQ(){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,page,section,JsonField.clear());}
    public DocumentChunksReadInput omitQ(){return new DocumentChunksReadInput(readerSourceConnections,offset,limit,page,section,null);}
}

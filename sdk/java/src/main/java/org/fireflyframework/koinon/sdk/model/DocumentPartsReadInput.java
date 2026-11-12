// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DocumentPartsReadInput contract. */
public record DocumentPartsReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("page") Integer page,
    @JsonProperty("page_size") Integer pageSize,
    @JsonProperty("kind") JsonField<DocumentPartSummaryKind> kind
) {

    public static DocumentPartsReadInput empty(){return new DocumentPartsReadInput(null,null,null,null);}
    public DocumentPartsReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new DocumentPartsReadInput(JsonField.of(value),page,pageSize,kind);}
    public DocumentPartsReadInput clearReaderSourceConnections(){return new DocumentPartsReadInput(JsonField.clear(),page,pageSize,kind);}
    public DocumentPartsReadInput omitReaderSourceConnections(){return new DocumentPartsReadInput(null,page,pageSize,kind);}
    public DocumentPartsReadInput withPage(Integer value){return new DocumentPartsReadInput(readerSourceConnections,value,pageSize,kind);}
    public DocumentPartsReadInput withPageSize(Integer value){return new DocumentPartsReadInput(readerSourceConnections,page,value,kind);}
    public DocumentPartsReadInput withKind(DocumentPartSummaryKind value){return new DocumentPartsReadInput(readerSourceConnections,page,pageSize,JsonField.of(value));}
    public DocumentPartsReadInput clearKind(){return new DocumentPartsReadInput(readerSourceConnections,page,pageSize,JsonField.clear());}
    public DocumentPartsReadInput omitKind(){return new DocumentPartsReadInput(readerSourceConnections,page,pageSize,null);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ReaderReadInput contract. */
public record ReaderReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections
) {

    public static ReaderReadInput empty(){return new ReaderReadInput(null);}
    public ReaderReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new ReaderReadInput(JsonField.of(value));}
    public ReaderReadInput clearReaderSourceConnections(){return new ReaderReadInput(JsonField.clear());}
    public ReaderReadInput omitReaderSourceConnections(){return new ReaderReadInput(null);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical LineageReadInput contract. */
public record LineageReadInput(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("asset_id") JsonField<String> assetId
) {

    public static LineageReadInput empty(){return new LineageReadInput(null,null);}
    public LineageReadInput withReaderSourceConnections(List<ReaderSourceSelection> value){return new LineageReadInput(JsonField.of(value),assetId);}
    public LineageReadInput clearReaderSourceConnections(){return new LineageReadInput(JsonField.clear(),assetId);}
    public LineageReadInput omitReaderSourceConnections(){return new LineageReadInput(null,assetId);}
    public LineageReadInput withAssetId(String value){return new LineageReadInput(readerSourceConnections,JsonField.of(value));}
    public LineageReadInput clearAssetId(){return new LineageReadInput(readerSourceConnections,JsonField.clear());}
    public LineageReadInput omitAssetId(){return new LineageReadInput(readerSourceConnections,null);}
}

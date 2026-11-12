// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AvailabilityRequest contract. */
public record AvailabilityRequest(
    @JsonProperty("reader_source_connections") JsonField<List<ReaderSourceSelection>> readerSourceConnections,
    @JsonProperty("asset_ids") List<String> assetIds,
    @JsonProperty("workspace_id") JsonField<String> workspaceId
) {
    public AvailabilityRequest {
        assetIds=assetIds==null?null:List.copyOf(assetIds);
    }

    public static AvailabilityRequest empty(){return new AvailabilityRequest(null,null,null);}
    public AvailabilityRequest withReaderSourceConnections(List<ReaderSourceSelection> value){return new AvailabilityRequest(JsonField.of(value),assetIds,workspaceId);}
    public AvailabilityRequest clearReaderSourceConnections(){return new AvailabilityRequest(JsonField.clear(),assetIds,workspaceId);}
    public AvailabilityRequest omitReaderSourceConnections(){return new AvailabilityRequest(null,assetIds,workspaceId);}
    public AvailabilityRequest withAssetIds(List<String> value){return new AvailabilityRequest(readerSourceConnections,value,workspaceId);}
    public AvailabilityRequest withWorkspaceId(String value){return new AvailabilityRequest(readerSourceConnections,assetIds,JsonField.of(value));}
    public AvailabilityRequest clearWorkspaceId(){return new AvailabilityRequest(readerSourceConnections,assetIds,JsonField.clear());}
    public AvailabilityRequest omitWorkspaceId(){return new AvailabilityRequest(readerSourceConnections,assetIds,null);}
}

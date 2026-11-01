// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AvailabilityRequest contract. */
public record AvailabilityRequest(
    @JsonProperty("asset_ids") List<String> assetIds,
    @JsonProperty("workspace_id") JsonField<String> workspaceId
) {
    public AvailabilityRequest {
        assetIds=assetIds==null?null:List.copyOf(assetIds);
    }

    public static AvailabilityRequest empty(){return new AvailabilityRequest(null,null);}
    public AvailabilityRequest withAssetIds(List<String> value){return new AvailabilityRequest(value,workspaceId);}
    public AvailabilityRequest withWorkspaceId(String value){return new AvailabilityRequest(assetIds,JsonField.of(value));}
    public AvailabilityRequest clearWorkspaceId(){return new AvailabilityRequest(assetIds,JsonField.clear());}
    public AvailabilityRequest omitWorkspaceId(){return new AvailabilityRequest(assetIds,null);}
}

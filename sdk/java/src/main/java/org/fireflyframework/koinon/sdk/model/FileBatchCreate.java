// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical FileBatchCreate contract. */
public record FileBatchCreate(
    @JsonProperty("destination") BulkDestination destination,
    @JsonProperty("processing_policy") FileBatchCapabilitiesProcessingPolicy processingPolicy,
    @JsonProperty("items") List<FileManifestItem> items
) {
    public FileBatchCreate {
        items=items==null?null:List.copyOf(items);
    }

    public static FileBatchCreate empty(){return new FileBatchCreate(null,null,null);}
    public FileBatchCreate withDestination(BulkDestination value){return new FileBatchCreate(value,processingPolicy,items);}
    public FileBatchCreate withProcessingPolicy(FileBatchCapabilitiesProcessingPolicy value){return new FileBatchCreate(destination,value,items);}
    public FileBatchCreate withItems(List<FileManifestItem> value){return new FileBatchCreate(destination,processingPolicy,value);}
}

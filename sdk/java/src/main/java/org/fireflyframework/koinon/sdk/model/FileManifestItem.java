// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical FileManifestItem contract. */
public record FileManifestItem(
    @JsonProperty("client_item_id") String clientItemId,
    @JsonProperty("filename") String filename,
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("size_bytes") Integer sizeBytes,
    @JsonProperty("sha256") String sha256
) {

    public static FileManifestItem empty(){return new FileManifestItem(null,null,null,null,null);}
    public FileManifestItem withClientItemId(String value){return new FileManifestItem(value,filename,mode,sizeBytes,sha256);}
    public FileManifestItem withFilename(String value){return new FileManifestItem(clientItemId,value,mode,sizeBytes,sha256);}
    public FileManifestItem withMode(AddKnowledgeMode value){return new FileManifestItem(clientItemId,filename,value,sizeBytes,sha256);}
    public FileManifestItem withSizeBytes(Integer value){return new FileManifestItem(clientItemId,filename,mode,value,sha256);}
    public FileManifestItem withSha256(String value){return new FileManifestItem(clientItemId,filename,mode,sizeBytes,value);}
}

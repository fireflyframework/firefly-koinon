// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ExternalFileChunkInput contract. */
public record ExternalFileChunkInput(
    @JsonProperty("index") Integer index,
    @JsonProperty("data_base64") String dataBase64,
    @JsonProperty("sha256") String sha256
) {

    public static ExternalFileChunkInput empty(){return new ExternalFileChunkInput(null,null,null);}
    public ExternalFileChunkInput withIndex(Integer value){return new ExternalFileChunkInput(value,dataBase64,sha256);}
    public ExternalFileChunkInput withDataBase64(String value){return new ExternalFileChunkInput(index,value,sha256);}
    public ExternalFileChunkInput withSha256(String value){return new ExternalFileChunkInput(index,dataBase64,value);}
}

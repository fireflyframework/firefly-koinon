// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentReingestInput contract. */
public record DocumentReingestInput(
    @JsonProperty("acknowledge_chunk_invalidation") Boolean acknowledgeChunkInvalidation
) {

    public static DocumentReingestInput empty(){return new DocumentReingestInput(null);}
    public DocumentReingestInput withAcknowledgeChunkInvalidation(Boolean value){return new DocumentReingestInput(value);}
}

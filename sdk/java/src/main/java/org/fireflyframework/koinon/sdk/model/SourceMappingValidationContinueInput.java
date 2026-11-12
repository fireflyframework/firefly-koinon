// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceMappingValidationContinueInput contract. */
public record SourceMappingValidationContinueInput(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("continuation_token") String continuationToken
) {

    public static SourceMappingValidationContinueInput empty(){return new SourceMappingValidationContinueInput(null,null);}
    public SourceMappingValidationContinueInput withExpectedRevision(Long value){return new SourceMappingValidationContinueInput(value,continuationToken);}
    public SourceMappingValidationContinueInput withContinuationToken(String value){return new SourceMappingValidationContinueInput(expectedRevision,value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceMappingValidationAbandonInput contract. */
public record SourceMappingValidationAbandonInput(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static SourceMappingValidationAbandonInput empty(){return new SourceMappingValidationAbandonInput(null);}
    public SourceMappingValidationAbandonInput withExpectedRevision(Long value){return new SourceMappingValidationAbandonInput(value);}
}

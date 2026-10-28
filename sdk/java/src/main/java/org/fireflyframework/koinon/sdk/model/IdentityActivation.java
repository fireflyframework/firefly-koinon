// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityActivation contract. */
public record IdentityActivation(
    @JsonProperty("expected_revision") Long expectedRevision,
    @JsonProperty("validation_id") String validationId
) {

    public static IdentityActivation empty(){return new IdentityActivation(null,null);}
    public IdentityActivation withExpectedRevision(Long value){return new IdentityActivation(value,validationId);}
    public IdentityActivation withValidationId(String value){return new IdentityActivation(expectedRevision,value);}
}

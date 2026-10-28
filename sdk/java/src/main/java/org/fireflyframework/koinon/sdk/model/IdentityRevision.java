// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityRevision contract. */
public record IdentityRevision(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static IdentityRevision empty(){return new IdentityRevision(null);}
    public IdentityRevision withExpectedRevision(Long value){return new IdentityRevision(value);}
}

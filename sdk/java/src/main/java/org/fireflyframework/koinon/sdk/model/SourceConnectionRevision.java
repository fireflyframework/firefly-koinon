// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceConnectionRevision contract. */
public record SourceConnectionRevision(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static SourceConnectionRevision empty(){return new SourceConnectionRevision(null);}
    public SourceConnectionRevision withExpectedRevision(Long value){return new SourceConnectionRevision(value);}
}

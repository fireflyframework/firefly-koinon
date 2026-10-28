// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeCancellation contract. */
public record KnowledgeCancellation(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static KnowledgeCancellation empty(){return new KnowledgeCancellation(null);}
    public KnowledgeCancellation withExpectedRevision(Long value){return new KnowledgeCancellation(value);}
}

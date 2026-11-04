// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical KnowledgeModeRevisionInput contract. */
public record KnowledgeModeRevisionInput(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static KnowledgeModeRevisionInput empty(){return new KnowledgeModeRevisionInput(null);}
    public KnowledgeModeRevisionInput withExpectedRevision(Long value){return new KnowledgeModeRevisionInput(value);}
}

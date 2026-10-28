// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IndexRevisionInput contract. */
public record IndexRevisionInput(
    @JsonProperty("expected_revision") Long expectedRevision
) {

    public static IndexRevisionInput empty(){return new IndexRevisionInput(null);}
    public IndexRevisionInput withExpectedRevision(Long value){return new IndexRevisionInput(value);}
}

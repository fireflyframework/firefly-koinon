// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical BulkAction contract. */
public record BulkAction(
    @JsonProperty("expected_revision") Integer expectedRevision
) {

    public static BulkAction empty(){return new BulkAction(null);}
    public BulkAction withExpectedRevision(Integer value){return new BulkAction(value);}
}

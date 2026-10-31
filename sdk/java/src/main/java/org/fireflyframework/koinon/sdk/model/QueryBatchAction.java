// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical QueryBatchAction contract. */
public record QueryBatchAction(
    @JsonProperty("expected_revision") Integer expectedRevision
) {

    public static QueryBatchAction empty(){return new QueryBatchAction(null);}
    public QueryBatchAction withExpectedRevision(Integer value){return new QueryBatchAction(value);}
}

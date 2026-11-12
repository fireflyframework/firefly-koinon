// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SourceControlInput contract. */
public record SourceControlInput(
    @JsonProperty("operation_id") String operationId,
    @JsonProperty("expected_revision") Integer expectedRevision
) {

    public static SourceControlInput empty(){return new SourceControlInput(null,null);}
    public SourceControlInput withOperationId(String value){return new SourceControlInput(value,expectedRevision);}
    public SourceControlInput withExpectedRevision(Integer value){return new SourceControlInput(operationId,value);}
}

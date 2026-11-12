// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OperationInput contract. */
public record OperationInput(
    @JsonProperty("operation_id") String operationId
) {

    public static OperationInput empty(){return new OperationInput(null);}
    public OperationInput withOperationId(String value){return new OperationInput(value);}
}

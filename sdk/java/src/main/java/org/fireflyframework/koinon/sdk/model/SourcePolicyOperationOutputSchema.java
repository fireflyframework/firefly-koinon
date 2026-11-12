// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourcePolicyOperationOutputSchema {
    KOINON_SOURCE_POLICY_OPERATION_V1("koinon.source-policy-operation.v1");
    private final String value;
    SourcePolicyOperationOutputSchema(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourcePolicyOperationOutputSchema from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourcePolicyOperationOutputSchema value: "+value);}
}

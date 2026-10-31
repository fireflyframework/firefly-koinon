// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum RlmToolReceiptResultKind {
    TOOL_RETURN("tool_return"),
    ACCEPTED_FINAL("accepted_final"),
    EXECUTION_FAILURE("execution_failure");
    private final String value;
    RlmToolReceiptResultKind(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static RlmToolReceiptResultKind from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown RlmToolReceiptResultKind value: "+value);}
}

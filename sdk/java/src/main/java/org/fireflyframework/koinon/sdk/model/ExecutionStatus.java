// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ExecutionStatus {
    OK("OK"),
    REFINED_OK("REFINED_OK"),
    FAILED("FAILED"),
    REJECTED_BY_FIREWALL("REJECTED_BY_FIREWALL");
    private final String value;
    ExecutionStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ExecutionStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ExecutionStatus value: "+value);}
}

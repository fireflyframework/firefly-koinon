// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceMappingValidationOutputState {
    SCANNING("scanning"),
    VERIFYING("verifying"),
    CHECKING_CHANGES("checking_changes"),
    COMPLETE("complete"),
    BLOCKED("blocked"),
    STALE("stale"),
    CLEANING("cleaning"),
    ABANDONED("abandoned"),
    EXPIRED("expired");
    private final String value;
    SourceMappingValidationOutputState(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceMappingValidationOutputState from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceMappingValidationOutputState value: "+value);}
}

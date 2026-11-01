// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum HealthComponentCoverage {
    COMPLETE("complete"),
    PARTIAL("partial"),
    UNAVAILABLE("unavailable");
    private final String value;
    HealthComponentCoverage(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static HealthComponentCoverage from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown HealthComponentCoverage value: "+value);}
}

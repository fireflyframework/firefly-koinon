// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum AvailabilityCapabilityState {
    READY("ready"),
    PENDING("pending"),
    UNAVAILABLE("unavailable"),
    UNKNOWN("unknown"),
    NOT_APPLICABLE("not_applicable");
    private final String value;
    AvailabilityCapabilityState(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static AvailabilityCapabilityState from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown AvailabilityCapabilityState value: "+value);}
}

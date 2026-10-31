// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ProfileFieldStatus {
    NOT_OBSERVED("not_observed"),
    CURRENT("current"),
    EMPTY("empty"),
    UNAVAILABLE("unavailable"),
    UNSUPPORTED("unsupported"),
    STALE("stale");
    private final String value;
    ProfileFieldStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ProfileFieldStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ProfileFieldStatus value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceMappingOutputStatus {
    REVIEWED("reviewed"),
    ACTIVE("active"),
    PAUSED("paused"),
    RECONNECT_REQUIRED("reconnect_required"),
    RETIRED("retired");
    private final String value;
    SourceMappingOutputStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceMappingOutputStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceMappingOutputStatus value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceRunOutputStatus {
    QUEUED("queued"),
    RUNNING("running"),
    RECONCILING("reconciling"),
    RECONNECT_REQUIRED("reconnect_required"),
    SUCCEEDED("succeeded"),
    PARTIAL("partial"),
    FAILED("failed"),
    CANCELLED("cancelled");
    private final String value;
    SourceRunOutputStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceRunOutputStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceRunOutputStatus value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum KnowledgeModeTransitionViewStatus {
    QUEUED("queued"),
    RUNNING("running"),
    FAILED("failed"),
    CANCELLED("cancelled"),
    SUPERSEDED("superseded"),
    SUCCEEDED("succeeded");
    private final String value;
    KnowledgeModeTransitionViewStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static KnowledgeModeTransitionViewStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown KnowledgeModeTransitionViewStatus value: "+value);}
}

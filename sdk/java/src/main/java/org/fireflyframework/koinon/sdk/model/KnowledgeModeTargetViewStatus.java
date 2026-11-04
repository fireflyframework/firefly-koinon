// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum KnowledgeModeTargetViewStatus {
    QUEUED("queued"),
    PREPARED("prepared"),
    READY("ready"),
    WAITING("waiting"),
    FAILED("failed"),
    EXCLUDED("excluded");
    private final String value;
    KnowledgeModeTargetViewStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static KnowledgeModeTargetViewStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown KnowledgeModeTargetViewStatus value: "+value);}
}

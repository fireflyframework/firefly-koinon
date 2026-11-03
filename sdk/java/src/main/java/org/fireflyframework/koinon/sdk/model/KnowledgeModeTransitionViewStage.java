// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum KnowledgeModeTransitionViewStage {
    DISCOVERY("discovery"),
    PREFLIGHT("preflight"),
    REPAIR_VIEWS("repair_views"),
    PREPARE_INDEXES("prepare_indexes"),
    VERIFY("verify"),
    ACTIVATE("activate");
    private final String value;
    KnowledgeModeTransitionViewStage(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static KnowledgeModeTransitionViewStage from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown KnowledgeModeTransitionViewStage value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum MappingReviewInputRemovalPolicy {
    RETIRE("retire"),
    PAUSE_FOR_REVIEW("pause_for_review");
    private final String value;
    MappingReviewInputRemovalPolicy(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static MappingReviewInputRemovalPolicy from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown MappingReviewInputRemovalPolicy value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ExternalReviewViewStatus {
    PREVIEW("preview"),
    COMMITTING("committing"),
    COMMITTED("committed"),
    CANCELLED("cancelled"),
    STALE("stale"),
    UNRESOLVED("unresolved");
    private final String value;
    ExternalReviewViewStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ExternalReviewViewStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ExternalReviewViewStatus value: "+value);}
}

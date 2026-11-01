// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum HealthComponentRemediation {
    NONE("none"),
    RETRY_READ("retry_read"),
    REVIEW_CONFIGURATION("review_configuration"),
    REVIEW_INDEXES("review_indexes"),
    REVIEW_INGESTION("review_ingestion"),
    REVIEW_COMMUNICATIONS("review_communications"),
    REVIEW_WORKER("review_worker");
    private final String value;
    HealthComponentRemediation(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static HealthComponentRemediation from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown HealthComponentRemediation value: "+value);}
}

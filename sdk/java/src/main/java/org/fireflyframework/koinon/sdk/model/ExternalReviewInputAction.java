// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ExternalReviewInputAction {
    CREATE_DRAFT("create_draft"),
    CREATE_PUBLISHED("create_published"),
    UPDATE_DRAFT("update_draft"),
    UPDATE_PUBLISHED("update_published"),
    PUBLISH_DRAFT("publish_draft");
    private final String value;
    ExternalReviewInputAction(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ExternalReviewInputAction from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ExternalReviewInputAction value: "+value);}
}

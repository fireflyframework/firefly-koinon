// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ProfileFieldName {
    DISPLAY_NAME("display_name"),
    AVATAR("avatar"),
    JOB_TITLE("job_title"),
    DEPARTMENT("department"),
    MANAGER("manager");
    private final String value;
    ProfileFieldName(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ProfileFieldName from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ProfileFieldName value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ActivitySummaryAudience {
    PERSONAL("personal"),
    ORGANIZATION_ADMINISTRATORS("organization_administrators");
    private final String value;
    ActivitySummaryAudience(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ActivitySummaryAudience from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ActivitySummaryAudience value: "+value);}
}

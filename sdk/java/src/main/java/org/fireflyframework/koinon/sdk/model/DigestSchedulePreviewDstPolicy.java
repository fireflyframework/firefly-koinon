// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum DigestSchedulePreviewDstPolicy {
    FIRST_VALID_MINUTE_EARLIER_FOLD("first_valid_minute_earlier_fold");
    private final String value;
    DigestSchedulePreviewDstPolicy(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static DigestSchedulePreviewDstPolicy from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown DigestSchedulePreviewDstPolicy value: "+value);}
}

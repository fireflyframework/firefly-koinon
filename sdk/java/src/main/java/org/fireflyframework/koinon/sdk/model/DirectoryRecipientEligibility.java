// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum DirectoryRecipientEligibility {
    ELIGIBLE("eligible"),
    ALREADY_HAS_ACCESS("already_has_access"),
    UNAVAILABLE("unavailable");
    private final String value;
    DirectoryRecipientEligibility(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static DirectoryRecipientEligibility from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown DirectoryRecipientEligibility value: "+value);}
}

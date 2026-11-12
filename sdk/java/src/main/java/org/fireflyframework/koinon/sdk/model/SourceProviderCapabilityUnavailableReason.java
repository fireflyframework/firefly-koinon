// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceProviderCapabilityUnavailableReason {
    DISABLED("disabled"),
    NOT_CONFIGURED("not_configured");
    private final String value;
    SourceProviderCapabilityUnavailableReason(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceProviderCapabilityUnavailableReason from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceProviderCapabilityUnavailableReason value: "+value);}
}

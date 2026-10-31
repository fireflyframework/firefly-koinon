// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ProfileObservationSource {
    DIRECTORY("directory"),
    VERIFIED_CLAIMS("verified_claims"),
    LOCAL("local"),
    PERSONAL("personal");
    private final String value;
    ProfileObservationSource(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ProfileObservationSource from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ProfileObservationSource value: "+value);}
}

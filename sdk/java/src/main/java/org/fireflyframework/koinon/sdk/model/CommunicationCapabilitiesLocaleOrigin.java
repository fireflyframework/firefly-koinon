// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum CommunicationCapabilitiesLocaleOrigin {
    USER("user"),
    ORGANIZATION("organization"),
    INSTALLATION("installation"),
    DEFAULT("default");
    private final String value;
    CommunicationCapabilitiesLocaleOrigin(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static CommunicationCapabilitiesLocaleOrigin from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown CommunicationCapabilitiesLocaleOrigin value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum TableProvenanceOperation {
    UPLOAD("upload"),
    REPLACE("replace"),
    REINGEST("reingest");
    private final String value;
    TableProvenanceOperation(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static TableProvenanceOperation from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown TableProvenanceOperation value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceMappingValidationItemCollision {
    NONE("none"),
    SOURCE_NAME("source_name"),
    DESTINATION_NAME("destination_name"),
    LOCAL_EDIT("local_edit");
    private final String value;
    SourceMappingValidationItemCollision(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceMappingValidationItemCollision from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceMappingValidationItemCollision value: "+value);}
}

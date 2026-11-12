// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceMappingValidationOutputReasonCode {
    SOURCE_NAME_COLLISION("SOURCE_NAME_COLLISION"),
    SOURCE_DESTINATION_COLLISION("SOURCE_DESTINATION_COLLISION"),
    SOURCE_LOCAL_EDIT("SOURCE_LOCAL_EDIT"),
    SOURCE_CHANGED("SOURCE_CHANGED"),
    SOURCE_AUTHORITY_CHANGED("SOURCE_AUTHORITY_CHANGED"),
    SOURCE_SCAN_LIMIT_EXCEEDED("SOURCE_SCAN_LIMIT_EXCEEDED"),
    SOURCE_VALIDATION_CAPACITY("SOURCE_VALIDATION_CAPACITY"),
    SOURCE_UNAVAILABLE("SOURCE_UNAVAILABLE"),
    SOURCE_VALIDATION_REFRESH_REQUIRED("SOURCE_VALIDATION_REFRESH_REQUIRED"),
    SOURCE_INVALID_SELECTION("SOURCE_INVALID_SELECTION");
    private final String value;
    SourceMappingValidationOutputReasonCode(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceMappingValidationOutputReasonCode from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceMappingValidationOutputReasonCode value: "+value);}
}

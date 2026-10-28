// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum FieldSchemaType {
    TEXT("text"),
    URL("url"),
    SECRET("secret"),
    STRING_LIST("string_list"),
    SELECT("select");
    private final String value;
    FieldSchemaType(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static FieldSchemaType from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown FieldSchemaType value: "+value);}
}

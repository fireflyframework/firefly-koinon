// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum AnswerPublicationFormat {
    VERIFIED_UNICODE_V1("verified-unicode-v1");
    private final String value;
    AnswerPublicationFormat(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static AnswerPublicationFormat from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown AnswerPublicationFormat value: "+value);}
}

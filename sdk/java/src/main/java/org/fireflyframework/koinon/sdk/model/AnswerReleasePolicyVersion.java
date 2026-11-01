// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum AnswerReleasePolicyVersion {
    KNOWLEDGE_ONLY_V1("knowledge-only-v1");
    private final String value;
    AnswerReleasePolicyVersion(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static AnswerReleasePolicyVersion from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown AnswerReleasePolicyVersion value: "+value);}
}

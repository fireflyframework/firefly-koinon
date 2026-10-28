// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum PrivateChunkViewOffsetBasis {
    NORMALIZED_TEXT_CODE_POINTS("normalized_text_code_points");
    private final String value;
    PrivateChunkViewOffsetBasis(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static PrivateChunkViewOffsetBasis from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown PrivateChunkViewOffsetBasis value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ProductHelpContextSelection {
    EXPLICIT_SELECTION("explicit_selection"),
    BROADER_SCOPE("broader_scope"),
    PRIVATE_ATTACHMENTS("private_attachments");
    private final String value;
    ProductHelpContextSelection(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ProductHelpContextSelection from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ProductHelpContextSelection value: "+value);}
}

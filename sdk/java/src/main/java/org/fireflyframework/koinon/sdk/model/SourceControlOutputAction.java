// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceControlOutputAction {
    SYNC("sync"),
    PAUSE("pause"),
    RESUME("resume"),
    CANCEL("cancel"),
    RETRY("retry"),
    RETIRE("retire");
    private final String value;
    SourceControlOutputAction(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceControlOutputAction from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceControlOutputAction value: "+value);}
}

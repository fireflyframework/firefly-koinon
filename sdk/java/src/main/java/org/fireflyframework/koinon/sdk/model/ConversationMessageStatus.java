// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ConversationMessageStatus {
    COMPLETED("completed"),
    FAILED("failed"),
    CANCELLED("cancelled");
    private final String value;
    ConversationMessageStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ConversationMessageStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ConversationMessageStatus value: "+value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum PrivateFileReceiptAvailability {
    AVAILABLE("available"),
    EXPIRED("expired"),
    DELETED("deleted"),
    CHANGED("changed"),
    UNAVAILABLE("unavailable");
    private final String value;
    PrivateFileReceiptAvailability(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static PrivateFileReceiptAvailability from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown PrivateFileReceiptAvailability value: "+value);}
}

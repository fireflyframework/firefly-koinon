// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum DeliveryRecordKind {
    INVITATION("invitation"),
    ACCESS_GRANTED("access_granted"),
    ROLE_CHANGED("role_changed"),
    ACCESS_REMOVED("access_removed"),
    SECURITY("security"),
    WELCOME("welcome"),
    DIGEST("digest");
    private final String value;
    DeliveryRecordKind(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static DeliveryRecordKind from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown DeliveryRecordKind value: "+value);}
}

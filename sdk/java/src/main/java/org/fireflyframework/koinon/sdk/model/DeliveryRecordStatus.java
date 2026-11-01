// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum DeliveryRecordStatus {
    QUEUED("queued"),
    SENDING("sending"),
    SENT("sent"),
    DELIVERED("delivered"),
    DEFERRED("deferred"),
    FAILED("failed"),
    SUPPRESSED("suppressed"),
    CANCELLED("cancelled"),
    UNKNOWN("unknown");
    private final String value;
    DeliveryRecordStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static DeliveryRecordStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown DeliveryRecordStatus value: "+value);}
}

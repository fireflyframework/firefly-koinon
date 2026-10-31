// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum FileBatchItemViewStatus {
    AWAITING_UPLOAD("awaiting_upload"),
    STAGED("staged"),
    QUEUED("queued"),
    RUNNING("running"),
    SUCCEEDED("succeeded"),
    FAILED("failed"),
    CANCELLED("cancelled"),
    RECONCILING("reconciling");
    private final String value;
    FileBatchItemViewStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static FileBatchItemViewStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown FileBatchItemViewStatus value: "+value);}
}

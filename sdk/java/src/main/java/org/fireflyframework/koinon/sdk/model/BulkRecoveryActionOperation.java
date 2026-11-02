// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum BulkRecoveryActionOperation {
    RETRY_PROCESSING("retry_processing"),
    FINALIZE_PUBLICATION("finalize_publication"),
    ACKNOWLEDGE_COMMIT("acknowledge_commit");
    private final String value;
    BulkRecoveryActionOperation(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static BulkRecoveryActionOperation from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown BulkRecoveryActionOperation value: "+value);}
}

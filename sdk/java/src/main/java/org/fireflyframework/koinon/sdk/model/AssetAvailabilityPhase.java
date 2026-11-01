// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum AssetAvailabilityPhase {
    UNKNOWN("unknown"),
    QUEUED("queued"),
    PROCESSING("processing"),
    INDEXING("indexing"),
    COMPLETE("complete"),
    FAILED("failed"),
    CANCELLED("cancelled"),
    RECONCILIATION_REQUIRED("reconciliation_required");
    private final String value;
    AssetAvailabilityPhase(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static AssetAvailabilityPhase from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown AssetAvailabilityPhase value: "+value);}
}

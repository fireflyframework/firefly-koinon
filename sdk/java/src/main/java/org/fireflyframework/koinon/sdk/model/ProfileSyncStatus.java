// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ProfileSyncStatus {
    NOT_CONFIGURED("not_configured"),
    NOT_BOUND("not_bound"),
    QUEUED("queued"),
    RUNNING("running"),
    CURRENT("current"),
    STALE("stale"),
    UNAVAILABLE("unavailable"),
    CONFLICT("conflict");
    private final String value;
    ProfileSyncStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ProfileSyncStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ProfileSyncStatus value: "+value);}
}

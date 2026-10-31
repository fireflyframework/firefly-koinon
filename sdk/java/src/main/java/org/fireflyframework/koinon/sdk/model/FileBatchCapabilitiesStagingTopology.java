// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum FileBatchCapabilitiesStagingTopology {
    SINGLE_HOST_SHARED_DURABLE_POSIX("single_host_shared_durable_posix"),
    SHARED_PRIVATE_OBJECT_STORE("shared_private_object_store");
    private final String value;
    FileBatchCapabilitiesStagingTopology(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static FileBatchCapabilitiesStagingTopology from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown FileBatchCapabilitiesStagingTopology value: "+value);}
}

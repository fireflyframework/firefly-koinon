// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum FileBatchCapabilitiesStagingBackend {
    PRIVATE_LOCAL_POSIX("private_local_posix"),
    PRIVATE_AZURE_BLOB("private_azure_blob"),
    PRIVATE_GCS_OBJECT("private_gcs_object");
    private final String value;
    FileBatchCapabilitiesStagingBackend(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static FileBatchCapabilitiesStagingBackend from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown FileBatchCapabilitiesStagingBackend value: "+value);}
}

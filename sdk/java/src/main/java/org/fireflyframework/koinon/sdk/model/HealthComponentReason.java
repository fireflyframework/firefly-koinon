// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum HealthComponentReason {
    DATABASE_OK("DATABASE_OK"),
    DATABASE_UNAVAILABLE("DATABASE_UNAVAILABLE"),
    RUNTIME_ROLE_UNVERIFIED("RUNTIME_ROLE_UNVERIFIED"),
    RUNTIME_ROLE_UNSAFE("RUNTIME_ROLE_UNSAFE"),
    MODULE_DISABLED("MODULE_DISABLED"),
    STORAGE_NOT_PROBED("STORAGE_NOT_PROBED"),
    INDEXES_VERIFIED("INDEXES_VERIFIED"),
    INDEXES_INCOMPLETE("INDEXES_INCOMPLETE"),
    INDEXES_NOT_PROBED("INDEXES_NOT_PROBED"),
    NO_INDEXES("NO_INDEXES"),
    INGESTION_STATE_OBSERVED("INGESTION_STATE_OBSERVED"),
    INGESTION_FAILURES("INGESTION_FAILURES"),
    MODEL_CONFIGURATION_PRESENT("MODEL_CONFIGURATION_PRESENT"),
    MODEL_CONFIGURATION_INCOMPLETE("MODEL_CONFIGURATION_INCOMPLETE"),
    PROVIDER_NOT_PROBED("PROVIDER_NOT_PROBED"),
    COMMUNICATIONS_DISABLED("COMMUNICATIONS_DISABLED"),
    COMMUNICATIONS_CONFIGURED("COMMUNICATIONS_CONFIGURED"),
    COMMUNICATIONS_INCOMPLETE("COMMUNICATIONS_INCOMPLETE"),
    WORKER_LIVENESS_UNKNOWN("WORKER_LIVENESS_UNKNOWN"),
    OBSERVATION_UNAVAILABLE("OBSERVATION_UNAVAILABLE"),
    OBSERVATION_BOUNDED("OBSERVATION_BOUNDED"),
    OBSERVATION_STALE("OBSERVATION_STALE");
    private final String value;
    HealthComponentReason(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static HealthComponentReason from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown HealthComponentReason value: "+value);}
}

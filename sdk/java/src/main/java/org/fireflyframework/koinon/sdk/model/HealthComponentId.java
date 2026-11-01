// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum HealthComponentId {
    DATABASE_PRIMARY("database-primary"),
    DATABASE_DOCUMENTS("database-documents"),
    DATABASE_DOCUMENTS_CONTROL("database-documents-control"),
    DATABASE_STRUCTURED("database-structured"),
    DATABASE_STRUCTURED_CONTROL("database-structured-control"),
    STORAGE_DOCUMENTS("storage-documents"),
    STORAGE_STRUCTURED("storage-structured"),
    INDEXES_DOCUMENTS("indexes-documents"),
    INDEXES_STRUCTURED("indexes-structured"),
    INGESTION_DOCUMENTS("ingestion-documents"),
    INGESTION_STRUCTURED("ingestion-structured"),
    MODEL_CONFIGURATION("model-configuration"),
    COMMUNICATIONS("communications"),
    WORKERS("workers");
    private final String value;
    HealthComponentId(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static HealthComponentId from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown HealthComponentId value: "+value);}
}

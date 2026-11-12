// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SourceRunItemStatus {
    OBSERVED("observed"),
    DOWNLOADING("downloading"),
    PROCESSING("processing"),
    SYNCHRONIZED("synchronized"),
    SEARCHABLE("searchable"),
    SKIPPED("skipped"),
    CONFLICT("conflict"),
    RETIRED("retired"),
    FAILED("failed"),
    INDETERMINATE("indeterminate");
    private final String value;
    SourceRunItemStatus(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SourceRunItemStatus from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SourceRunItemStatus value: "+value);}
}

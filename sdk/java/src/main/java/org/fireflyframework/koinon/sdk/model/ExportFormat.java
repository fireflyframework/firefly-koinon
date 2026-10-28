// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ExportFormat {
    MARKDOWN("markdown"),
    JSON("json"),
    PARQUET("parquet"),
    CSV("csv"),
    JSONL("jsonl");
    private final String value;
    ExportFormat(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ExportFormat from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ExportFormat value: "+value);}
}

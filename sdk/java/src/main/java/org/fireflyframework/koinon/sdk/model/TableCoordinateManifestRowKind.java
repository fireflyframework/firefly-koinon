// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum TableCoordinateManifestRowKind {
    RECORD("record"),
    SHEET_ROW("sheet_row"),
    JSON_ARRAY("json_array"),
    JSONL_RECORD("jsonl_record"),
    SINGLE_OBJECT("single_object");
    private final String value;
    TableCoordinateManifestRowKind(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static TableCoordinateManifestRowKind from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown TableCoordinateManifestRowKind value: "+value);}
}

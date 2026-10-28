// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum ToolActivityToolName {
    SEARCH_KNOWLEDGE("search_knowledge"),
    INSPECT_SCHEMA("inspect_schema"),
    QUERY_DATASET("query_dataset"),
    SEARCH_PRIVATE_ATTACHMENTS("search_private_attachments"),
    PROPOSE_CATALOG_UPDATE("propose_catalog_update");
    private final String value;
    ToolActivityToolName(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static ToolActivityToolName from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown ToolActivityToolName value: "+value);}
}

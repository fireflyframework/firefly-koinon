// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum McpOAuthScope {
    CATALOG_READ("catalog:read"),
    CATALOG_WRITE("catalog:write"),
    INGEST_WRITE("ingest:write"),
    KNOWLEDGE_SEARCH("knowledge:search"),
    QUERY_EXECUTE("query:execute"),
    CHAT_USE("chat:use"),
    EVIDENCE_READ("evidence:read"),
    ACTIVITY_READ("activity:read");
    private final String value;
    McpOAuthScope(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static McpOAuthScope from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown McpOAuthScope value: "+value);}
}

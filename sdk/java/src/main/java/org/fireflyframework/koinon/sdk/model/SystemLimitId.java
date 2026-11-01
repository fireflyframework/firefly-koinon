// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum SystemLimitId {
    API_CAPACITY("api_capacity"),
    WORKER_CAPACITY("worker_capacity"),
    WORKER_CONCURRENCY("worker_concurrency"),
    MAX_INDEX_WORKSPACES("max_index_workspaces"),
    MCP_MAX_CONCURRENCY("mcp_max_concurrency"),
    MCP_MAX_REQUEST_BYTES("mcp_max_request_bytes"),
    MCP_MAX_RESPONSE_BYTES("mcp_max_response_bytes"),
    INGESTION_RAW_MAX_BYTES("ingestion_raw_max_bytes"),
    INGESTION_SCRATCH_MAX_BYTES("ingestion_scratch_max_bytes"),
    INGESTION_CHILD_RSS_MAX_BYTES("ingestion_child_rss_max_bytes");
    private final String value;
    SystemLimitId(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static SystemLimitId from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown SystemLimitId value: "+value);}
}

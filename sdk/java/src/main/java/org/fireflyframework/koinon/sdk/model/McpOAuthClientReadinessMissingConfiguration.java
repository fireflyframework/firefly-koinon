// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;



public enum McpOAuthClientReadinessMissingConfiguration {
    MCP_ENDPOINT("mcp_endpoint"),
    OAUTH_ENABLED("oauth_enabled"),
    OAUTH_ENCRYPTION_KEY("oauth_encryption_key");
    private final String value;
    McpOAuthClientReadinessMissingConfiguration(String value){this.value=value;}
    @JsonValue public String value(){return value;}
    @JsonCreator public static McpOAuthClientReadinessMissingConfiguration from(String value){for(var candidate:values())if(candidate.value.equals(value))return candidate;throw new IllegalArgumentException("Unknown McpOAuthClientReadinessMissingConfiguration value: "+value);}
}

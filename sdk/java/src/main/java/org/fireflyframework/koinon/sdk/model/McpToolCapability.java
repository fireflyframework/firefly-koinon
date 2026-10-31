// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpToolCapability contract. */
public record McpToolCapability(
    @JsonProperty("name") String name,
    @JsonProperty("required_scopes") List<String> requiredScopes,
    @JsonProperty("access") McpToolCapabilityAccess access,
    @JsonProperty("requires_app") Boolean requiresApp
) {
    public McpToolCapability {
        requiredScopes=requiredScopes==null?null:List.copyOf(requiredScopes);
    }

}

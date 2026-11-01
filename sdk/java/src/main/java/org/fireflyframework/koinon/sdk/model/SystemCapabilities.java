// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical SystemCapabilities contract. */
public record SystemCapabilities(
    @JsonProperty("knowledge_enabled") Boolean knowledgeEnabled,
    @JsonProperty("mcp_enabled") Boolean mcpEnabled,
    @JsonProperty("communications_enabled") Boolean communicationsEnabled,
    @JsonProperty("scheduled_consumers_enabled") Boolean scheduledConsumersEnabled
) {

}

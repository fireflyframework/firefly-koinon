// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationChatSettings contract. */
public record OrganizationChatSettings(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("default_agent_id") String defaultAgentId,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("memory") OrganizationMemoryPolicy memory,
    @JsonProperty("can_run") Boolean canRun,
    @JsonProperty("status") OrganizationChatSettingsStatus status
) {
    public OrganizationChatSettings(String tenantId, String defaultAgentId, Integer revision, Boolean configured, Boolean canRun, OrganizationChatSettingsStatus status){this(tenantId,defaultAgentId,revision,configured,null,canRun,status);}

}

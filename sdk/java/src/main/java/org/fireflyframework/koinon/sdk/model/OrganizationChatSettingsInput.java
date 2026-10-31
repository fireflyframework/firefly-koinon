// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationChatSettingsInput contract. */
public record OrganizationChatSettingsInput(
    @JsonProperty("default_agent_id") JsonField<String> defaultAgentId,
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("memory") OrganizationMemoryPolicyInput memory
) {
    public OrganizationChatSettingsInput(JsonField<String> defaultAgentId, Integer expectedRevision){this(defaultAgentId,expectedRevision,null);}

    public static OrganizationChatSettingsInput empty(){return new OrganizationChatSettingsInput(null,null,null);}
    public OrganizationChatSettingsInput withDefaultAgentId(String value){return new OrganizationChatSettingsInput(JsonField.of(value),expectedRevision,memory);}
    public OrganizationChatSettingsInput clearDefaultAgentId(){return new OrganizationChatSettingsInput(JsonField.clear(),expectedRevision,memory);}
    public OrganizationChatSettingsInput omitDefaultAgentId(){return new OrganizationChatSettingsInput(null,expectedRevision,memory);}
    public OrganizationChatSettingsInput withExpectedRevision(Integer value){return new OrganizationChatSettingsInput(defaultAgentId,value,memory);}
    public OrganizationChatSettingsInput withMemory(OrganizationMemoryPolicyInput value){return new OrganizationChatSettingsInput(defaultAgentId,expectedRevision,value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationChatSettingsInput contract. */
public record OrganizationChatSettingsInput(
    @JsonProperty("default_agent_id") JsonField<String> defaultAgentId,
    @JsonProperty("expected_revision") Integer expectedRevision
) {

    public static OrganizationChatSettingsInput empty(){return new OrganizationChatSettingsInput(null,null);}
    public OrganizationChatSettingsInput withDefaultAgentId(String value){return new OrganizationChatSettingsInput(JsonField.of(value),expectedRevision);}
    public OrganizationChatSettingsInput clearDefaultAgentId(){return new OrganizationChatSettingsInput(JsonField.clear(),expectedRevision);}
    public OrganizationChatSettingsInput omitDefaultAgentId(){return new OrganizationChatSettingsInput(null,expectedRevision);}
    public OrganizationChatSettingsInput withExpectedRevision(Integer value){return new OrganizationChatSettingsInput(defaultAgentId,value);}
}

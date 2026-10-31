// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationMemoryPolicyInput contract. */
public record OrganizationMemoryPolicyInput(
    @JsonProperty("allow_project_memory") Boolean allowProjectMemory,
    @JsonProperty("max_history_messages") Integer maxHistoryMessages,
    @JsonProperty("max_history_tokens") Integer maxHistoryTokens,
    @JsonProperty("max_project_memory_messages") Integer maxProjectMemoryMessages
) {

    public static OrganizationMemoryPolicyInput empty(){return new OrganizationMemoryPolicyInput(null,null,null,null);}
    public OrganizationMemoryPolicyInput withAllowProjectMemory(Boolean value){return new OrganizationMemoryPolicyInput(value,maxHistoryMessages,maxHistoryTokens,maxProjectMemoryMessages);}
    public OrganizationMemoryPolicyInput withMaxHistoryMessages(Integer value){return new OrganizationMemoryPolicyInput(allowProjectMemory,value,maxHistoryTokens,maxProjectMemoryMessages);}
    public OrganizationMemoryPolicyInput withMaxHistoryTokens(Integer value){return new OrganizationMemoryPolicyInput(allowProjectMemory,maxHistoryMessages,value,maxProjectMemoryMessages);}
    public OrganizationMemoryPolicyInput withMaxProjectMemoryMessages(Integer value){return new OrganizationMemoryPolicyInput(allowProjectMemory,maxHistoryMessages,maxHistoryTokens,value);}
}

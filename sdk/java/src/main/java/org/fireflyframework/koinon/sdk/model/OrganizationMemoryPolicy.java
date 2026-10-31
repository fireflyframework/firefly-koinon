// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationMemoryPolicy contract. */
public record OrganizationMemoryPolicy(
    @JsonProperty("allow_project_memory") Boolean allowProjectMemory,
    @JsonProperty("max_history_messages") Integer maxHistoryMessages,
    @JsonProperty("max_history_tokens") Integer maxHistoryTokens,
    @JsonProperty("max_project_memory_messages") Integer maxProjectMemoryMessages
) {

    public static OrganizationMemoryPolicy empty(){return new OrganizationMemoryPolicy(null,null,null,null);}
    public OrganizationMemoryPolicy withAllowProjectMemory(Boolean value){return new OrganizationMemoryPolicy(value,maxHistoryMessages,maxHistoryTokens,maxProjectMemoryMessages);}
    public OrganizationMemoryPolicy withMaxHistoryMessages(Integer value){return new OrganizationMemoryPolicy(allowProjectMemory,value,maxHistoryTokens,maxProjectMemoryMessages);}
    public OrganizationMemoryPolicy withMaxHistoryTokens(Integer value){return new OrganizationMemoryPolicy(allowProjectMemory,maxHistoryMessages,value,maxProjectMemoryMessages);}
    public OrganizationMemoryPolicy withMaxProjectMemoryMessages(Integer value){return new OrganizationMemoryPolicy(allowProjectMemory,maxHistoryMessages,maxHistoryTokens,value);}
}

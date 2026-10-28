// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityMapping contract. */
public record IdentityMapping(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("group_id") String groupId,
    @JsonProperty("group_name") String groupName,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("revision") Long revision
) {

}

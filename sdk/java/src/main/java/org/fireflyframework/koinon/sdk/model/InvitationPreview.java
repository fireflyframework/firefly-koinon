// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical InvitationPreview contract. */
public record InvitationPreview(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("tenant_name") String tenantName,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("workspace_name") String workspaceName,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("expires_at") Instant expiresAt
) {

}

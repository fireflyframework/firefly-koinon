// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical Invitation contract. */
public record Invitation(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("label") String label,
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("status") InvitationStatus status,
    @JsonProperty("accepted_at") String acceptedAt,
    @JsonProperty("accepted_by") String acceptedBy
) {

}

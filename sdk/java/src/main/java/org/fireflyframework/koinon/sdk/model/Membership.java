// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical Membership contract. */
public record Membership(
    @JsonProperty("managed") Boolean managed,
    @JsonProperty("origin") MembershipOrigin origin,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("source_name") String sourceName,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("id") String id,
    @JsonProperty("subject") String subject,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("active") Boolean active
) {

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.Map;



/** Typed canonical InvitationReview contract. */
public record InvitationReview(
    @JsonProperty("action_reasons") Map<String,EmailInvitationActionReasons> actionReasons,
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("organization_name") String organizationName,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("workspace_name") String workspaceName,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("status") EmailInvitationStatus status,
    @JsonProperty("can_accept") Boolean canAccept,
    @JsonProperty("can_decline") Boolean canDecline,
    @JsonProperty("binding") InvitationReviewBinding binding
) {
    public InvitationReview {
        actionReasons=actionReasons==null?null:Map.copyOf(actionReasons);
    }

}

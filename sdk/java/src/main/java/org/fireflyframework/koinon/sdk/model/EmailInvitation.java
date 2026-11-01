// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;
import java.util.Map;



/** Typed canonical EmailInvitation contract. */
public record EmailInvitation(
    @JsonProperty("action_reasons") Map<String,EmailInvitationActionReasons> actionReasons,
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("organization_name") String organizationName,
    @JsonProperty("workspace_name") String workspaceName,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("recipient_display_name") String recipientDisplayName,
    @JsonProperty("recipient_email") String recipientEmail,
    @JsonProperty("provider_label") String providerLabel,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("status") EmailInvitationStatus status,
    @JsonProperty("accepted_at") Instant acceptedAt,
    @JsonProperty("declined_at") Instant declinedAt,
    @JsonProperty("revoked_at") Instant revokedAt,
    @JsonProperty("delivery") InvitationDelivery delivery,
    @JsonProperty("allowed_actions") List<EmailInvitationAllowedActions> allowedActions
) {
    public EmailInvitation {
        actionReasons=actionReasons==null?null:Map.copyOf(actionReasons);
        allowedActions=allowedActions==null?null:List.copyOf(allowedActions);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical EmailInvitationInput contract. */
public record EmailInvitationInput(
    @JsonProperty("recipient_ref") String recipientRef,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("expires_in_hours") Integer expiresInHours,
    @JsonProperty("message") String message
) {

    public static EmailInvitationInput empty(){return new EmailInvitationInput(null,null,null,null,null);}
    public EmailInvitationInput withRecipientRef(String value){return new EmailInvitationInput(value,role,workspaceId,expiresInHours,message);}
    public EmailInvitationInput withRole(MembershipRole value){return new EmailInvitationInput(recipientRef,value,workspaceId,expiresInHours,message);}
    public EmailInvitationInput withWorkspaceId(String value){return new EmailInvitationInput(recipientRef,role,JsonField.of(value),expiresInHours,message);}
    public EmailInvitationInput clearWorkspaceId(){return new EmailInvitationInput(recipientRef,role,JsonField.clear(),expiresInHours,message);}
    public EmailInvitationInput omitWorkspaceId(){return new EmailInvitationInput(recipientRef,role,null,expiresInHours,message);}
    public EmailInvitationInput withExpiresInHours(Integer value){return new EmailInvitationInput(recipientRef,role,workspaceId,value,message);}
    public EmailInvitationInput withMessage(String value){return new EmailInvitationInput(recipientRef,role,workspaceId,expiresInHours,value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical InvitationInput contract. */
public record InvitationInput(
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("expires_in_hours") Integer expiresInHours,
    @JsonProperty("label") String label
) {

    public static InvitationInput empty(){return new InvitationInput(null,null,null,null);}
    public InvitationInput withRole(MembershipRole value){return new InvitationInput(value,workspaceId,expiresInHours,label);}
    public InvitationInput withWorkspaceId(String value){return new InvitationInput(role,JsonField.of(value),expiresInHours,label);}
    public InvitationInput clearWorkspaceId(){return new InvitationInput(role,JsonField.clear(),expiresInHours,label);}
    public InvitationInput omitWorkspaceId(){return new InvitationInput(role,null,expiresInHours,label);}
    public InvitationInput withExpiresInHours(Integer value){return new InvitationInput(role,workspaceId,value,label);}
    public InvitationInput withLabel(String value){return new InvitationInput(role,workspaceId,expiresInHours,value);}
}

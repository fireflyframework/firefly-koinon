// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical IdentityMappingInput contract. */
public record IdentityMappingInput(
    @JsonProperty("group_id") String groupId,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("workspace_id") JsonField<String> workspaceId,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("expected_revision") JsonField<Long> expectedRevision
) {

    public static IdentityMappingInput empty(){return new IdentityMappingInput(null,null,null,null,null);}
    public IdentityMappingInput withGroupId(String value){return new IdentityMappingInput(value,role,workspaceId,enabled,expectedRevision);}
    public IdentityMappingInput withRole(MembershipRole value){return new IdentityMappingInput(groupId,value,workspaceId,enabled,expectedRevision);}
    public IdentityMappingInput withWorkspaceId(String value){return new IdentityMappingInput(groupId,role,JsonField.of(value),enabled,expectedRevision);}
    public IdentityMappingInput clearWorkspaceId(){return new IdentityMappingInput(groupId,role,JsonField.clear(),enabled,expectedRevision);}
    public IdentityMappingInput omitWorkspaceId(){return new IdentityMappingInput(groupId,role,null,enabled,expectedRevision);}
    public IdentityMappingInput withEnabled(Boolean value){return new IdentityMappingInput(groupId,role,workspaceId,value,expectedRevision);}
    public IdentityMappingInput withExpectedRevision(Long value){return new IdentityMappingInput(groupId,role,workspaceId,enabled,JsonField.of(value));}
    public IdentityMappingInput clearExpectedRevision(){return new IdentityMappingInput(groupId,role,workspaceId,enabled,JsonField.clear());}
    public IdentityMappingInput omitExpectedRevision(){return new IdentityMappingInput(groupId,role,workspaceId,enabled,null);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical MemberInput contract. */
public record MemberInput(
    @JsonProperty("subject") String subject,
    @JsonProperty("role") MembershipRole role,
    @JsonProperty("workspace_id") JsonField<String> workspaceId
) {

    public static MemberInput empty(){return new MemberInput(null,null,null);}
    public MemberInput withSubject(String value){return new MemberInput(value,role,workspaceId);}
    public MemberInput withRole(MembershipRole value){return new MemberInput(subject,value,workspaceId);}
    public MemberInput withWorkspaceId(String value){return new MemberInput(subject,role,JsonField.of(value));}
    public MemberInput clearWorkspaceId(){return new MemberInput(subject,role,JsonField.clear());}
    public MemberInput omitWorkspaceId(){return new MemberInput(subject,role,null);}
}

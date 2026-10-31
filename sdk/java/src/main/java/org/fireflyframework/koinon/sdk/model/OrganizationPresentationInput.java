// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationPresentationInput contract. */
public record OrganizationPresentationInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("name_mode") ProfilePresentationMode nameMode,
    @JsonProperty("avatar_mode") ProfilePresentationMode avatarMode
) {

    public static OrganizationPresentationInput empty(){return new OrganizationPresentationInput(null,null,null);}
    public OrganizationPresentationInput withExpectedRevision(Integer value){return new OrganizationPresentationInput(value,nameMode,avatarMode);}
    public OrganizationPresentationInput withNameMode(ProfilePresentationMode value){return new OrganizationPresentationInput(expectedRevision,value,avatarMode);}
    public OrganizationPresentationInput withAvatarMode(ProfilePresentationMode value){return new OrganizationPresentationInput(expectedRevision,nameMode,value);}
}

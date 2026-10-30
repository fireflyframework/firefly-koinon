// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationDirectorySettingsInput contract. */
public record OrganizationDirectorySettingsInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("visibility") OrganizationDirectoryVisibility visibility
) {

    public static OrganizationDirectorySettingsInput empty(){return new OrganizationDirectorySettingsInput(null,null);}
    public OrganizationDirectorySettingsInput withExpectedRevision(Integer value){return new OrganizationDirectorySettingsInput(value,visibility);}
    public OrganizationDirectorySettingsInput withVisibility(OrganizationDirectoryVisibility value){return new OrganizationDirectorySettingsInput(expectedRevision,value);}
}

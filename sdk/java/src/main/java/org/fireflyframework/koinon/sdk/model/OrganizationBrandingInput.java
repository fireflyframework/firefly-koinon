// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationBrandingInput contract. */
public record OrganizationBrandingInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("branding") BrandingValues branding
) {

    public static OrganizationBrandingInput empty(){return new OrganizationBrandingInput(null,null);}
    public OrganizationBrandingInput withExpectedRevision(Integer value){return new OrganizationBrandingInput(value,branding);}
    public OrganizationBrandingInput withBranding(BrandingValues value){return new OrganizationBrandingInput(expectedRevision,value);}
}

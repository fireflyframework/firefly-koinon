// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationProfileMappingInput contract. */
public record OrganizationProfileMappingInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("fields") OrganizationProfileFields fields
) {

    public static OrganizationProfileMappingInput empty(){return new OrganizationProfileMappingInput(null,null,null);}
    public OrganizationProfileMappingInput withExpectedRevision(Integer value){return new OrganizationProfileMappingInput(value,enabled,fields);}
    public OrganizationProfileMappingInput withEnabled(Boolean value){return new OrganizationProfileMappingInput(expectedRevision,value,fields);}
    public OrganizationProfileMappingInput withFields(OrganizationProfileFields value){return new OrganizationProfileMappingInput(expectedRevision,enabled,value);}
}

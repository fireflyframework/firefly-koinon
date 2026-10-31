// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationProfileMappingInput contract. */
public record OrganizationProfileMappingInput(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("fields") OrganizationProfileFields fields,
    @JsonProperty("profile_sync") JsonField<CorporateProfileSyncPolicy> profileSync
) {

    public static OrganizationProfileMappingInput empty(){return new OrganizationProfileMappingInput(null,null,null,null);}
    public OrganizationProfileMappingInput withExpectedRevision(Integer value){return new OrganizationProfileMappingInput(value,enabled,fields,profileSync);}
    public OrganizationProfileMappingInput withEnabled(Boolean value){return new OrganizationProfileMappingInput(expectedRevision,value,fields,profileSync);}
    public OrganizationProfileMappingInput withFields(OrganizationProfileFields value){return new OrganizationProfileMappingInput(expectedRevision,enabled,value,profileSync);}
    public OrganizationProfileMappingInput withProfileSync(CorporateProfileSyncPolicy value){return new OrganizationProfileMappingInput(expectedRevision,enabled,fields,JsonField.of(value));}
    public OrganizationProfileMappingInput clearProfileSync(){return new OrganizationProfileMappingInput(expectedRevision,enabled,fields,JsonField.clear());}
    public OrganizationProfileMappingInput omitProfileSync(){return new OrganizationProfileMappingInput(expectedRevision,enabled,fields,null);}
}

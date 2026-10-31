// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationUnitInput contract. */
public record OrganizationUnitInput(
    @JsonProperty("name") String name,
    @JsonProperty("kind") OrganizationUnitKind kind,
    @JsonProperty("parent_id") JsonField<String> parentId,
    @JsonProperty("provider_id") JsonField<String> providerId,
    @JsonProperty("external_key") JsonField<String> externalKey
) {

    public static OrganizationUnitInput empty(){return new OrganizationUnitInput(null,null,null,null,null);}
    public OrganizationUnitInput withName(String value){return new OrganizationUnitInput(value,kind,parentId,providerId,externalKey);}
    public OrganizationUnitInput withKind(OrganizationUnitKind value){return new OrganizationUnitInput(name,value,parentId,providerId,externalKey);}
    public OrganizationUnitInput withParentId(String value){return new OrganizationUnitInput(name,kind,JsonField.of(value),providerId,externalKey);}
    public OrganizationUnitInput clearParentId(){return new OrganizationUnitInput(name,kind,JsonField.clear(),providerId,externalKey);}
    public OrganizationUnitInput omitParentId(){return new OrganizationUnitInput(name,kind,null,providerId,externalKey);}
    public OrganizationUnitInput withProviderId(String value){return new OrganizationUnitInput(name,kind,parentId,JsonField.of(value),externalKey);}
    public OrganizationUnitInput clearProviderId(){return new OrganizationUnitInput(name,kind,parentId,JsonField.clear(),externalKey);}
    public OrganizationUnitInput omitProviderId(){return new OrganizationUnitInput(name,kind,parentId,null,externalKey);}
    public OrganizationUnitInput withExternalKey(String value){return new OrganizationUnitInput(name,kind,parentId,providerId,JsonField.of(value));}
    public OrganizationUnitInput clearExternalKey(){return new OrganizationUnitInput(name,kind,parentId,providerId,JsonField.clear());}
    public OrganizationUnitInput omitExternalKey(){return new OrganizationUnitInput(name,kind,parentId,providerId,null);}
}

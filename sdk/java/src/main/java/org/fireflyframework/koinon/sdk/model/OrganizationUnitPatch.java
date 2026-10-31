// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationUnitPatch contract. */
public record OrganizationUnitPatch(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("kind") JsonField<OrganizationUnitKind> kind,
    @JsonProperty("parent_id") JsonField<String> parentId
) {

    public static OrganizationUnitPatch empty(){return new OrganizationUnitPatch(null,null,null,null);}
    public OrganizationUnitPatch withExpectedRevision(Integer value){return new OrganizationUnitPatch(value,name,kind,parentId);}
    public OrganizationUnitPatch withName(String value){return new OrganizationUnitPatch(expectedRevision,JsonField.of(value),kind,parentId);}
    public OrganizationUnitPatch clearName(){return new OrganizationUnitPatch(expectedRevision,JsonField.clear(),kind,parentId);}
    public OrganizationUnitPatch omitName(){return new OrganizationUnitPatch(expectedRevision,null,kind,parentId);}
    public OrganizationUnitPatch withKind(OrganizationUnitKind value){return new OrganizationUnitPatch(expectedRevision,name,JsonField.of(value),parentId);}
    public OrganizationUnitPatch clearKind(){return new OrganizationUnitPatch(expectedRevision,name,JsonField.clear(),parentId);}
    public OrganizationUnitPatch omitKind(){return new OrganizationUnitPatch(expectedRevision,name,null,parentId);}
    public OrganizationUnitPatch withParentId(String value){return new OrganizationUnitPatch(expectedRevision,name,kind,JsonField.of(value));}
    public OrganizationUnitPatch clearParentId(){return new OrganizationUnitPatch(expectedRevision,name,kind,JsonField.clear());}
    public OrganizationUnitPatch omitParentId(){return new OrganizationUnitPatch(expectedRevision,name,kind,null);}
}

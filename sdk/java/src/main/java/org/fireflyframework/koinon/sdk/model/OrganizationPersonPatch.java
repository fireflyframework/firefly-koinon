// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationPersonPatch contract. */
public record OrganizationPersonPatch(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("job_title") JsonField<String> jobTitle,
    @JsonProperty("unit_id") JsonField<String> unitId,
    @JsonProperty("manager_id") JsonField<String> managerId,
    @JsonProperty("manage_locally") Boolean manageLocally,
    @JsonProperty("managed_provider_id") JsonField<String> managedProviderId
) {

    public static OrganizationPersonPatch empty(){return new OrganizationPersonPatch(null,null,null,null,null,null);}
    public OrganizationPersonPatch withExpectedRevision(Integer value){return new OrganizationPersonPatch(value,jobTitle,unitId,managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch withJobTitle(String value){return new OrganizationPersonPatch(expectedRevision,JsonField.of(value),unitId,managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch clearJobTitle(){return new OrganizationPersonPatch(expectedRevision,JsonField.clear(),unitId,managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch omitJobTitle(){return new OrganizationPersonPatch(expectedRevision,null,unitId,managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch withUnitId(String value){return new OrganizationPersonPatch(expectedRevision,jobTitle,JsonField.of(value),managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch clearUnitId(){return new OrganizationPersonPatch(expectedRevision,jobTitle,JsonField.clear(),managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch omitUnitId(){return new OrganizationPersonPatch(expectedRevision,jobTitle,null,managerId,manageLocally,managedProviderId);}
    public OrganizationPersonPatch withManagerId(String value){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,JsonField.of(value),manageLocally,managedProviderId);}
    public OrganizationPersonPatch clearManagerId(){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,JsonField.clear(),manageLocally,managedProviderId);}
    public OrganizationPersonPatch omitManagerId(){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,null,manageLocally,managedProviderId);}
    public OrganizationPersonPatch withManageLocally(Boolean value){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,managerId,value,managedProviderId);}
    public OrganizationPersonPatch withManagedProviderId(String value){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,managerId,manageLocally,JsonField.of(value));}
    public OrganizationPersonPatch clearManagedProviderId(){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,managerId,manageLocally,JsonField.clear());}
    public OrganizationPersonPatch omitManagedProviderId(){return new OrganizationPersonPatch(expectedRevision,jobTitle,unitId,managerId,manageLocally,null);}
}

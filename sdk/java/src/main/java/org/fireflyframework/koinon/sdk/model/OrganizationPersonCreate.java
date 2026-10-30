// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationPersonCreate contract. */
public record OrganizationPersonCreate(
    @JsonProperty("profile_id") JsonField<String> profileId,
    @JsonProperty("subject") JsonField<String> subject,
    @JsonProperty("job_title") JsonField<String> jobTitle,
    @JsonProperty("unit_id") JsonField<String> unitId,
    @JsonProperty("manager_id") JsonField<String> managerId
) {

    public static OrganizationPersonCreate empty(){return new OrganizationPersonCreate(null,null,null,null,null);}
    public OrganizationPersonCreate withProfileId(String value){return new OrganizationPersonCreate(JsonField.of(value),subject,jobTitle,unitId,managerId);}
    public OrganizationPersonCreate clearProfileId(){return new OrganizationPersonCreate(JsonField.clear(),subject,jobTitle,unitId,managerId);}
    public OrganizationPersonCreate omitProfileId(){return new OrganizationPersonCreate(null,subject,jobTitle,unitId,managerId);}
    public OrganizationPersonCreate withSubject(String value){return new OrganizationPersonCreate(profileId,JsonField.of(value),jobTitle,unitId,managerId);}
    public OrganizationPersonCreate clearSubject(){return new OrganizationPersonCreate(profileId,JsonField.clear(),jobTitle,unitId,managerId);}
    public OrganizationPersonCreate omitSubject(){return new OrganizationPersonCreate(profileId,null,jobTitle,unitId,managerId);}
    public OrganizationPersonCreate withJobTitle(String value){return new OrganizationPersonCreate(profileId,subject,JsonField.of(value),unitId,managerId);}
    public OrganizationPersonCreate clearJobTitle(){return new OrganizationPersonCreate(profileId,subject,JsonField.clear(),unitId,managerId);}
    public OrganizationPersonCreate omitJobTitle(){return new OrganizationPersonCreate(profileId,subject,null,unitId,managerId);}
    public OrganizationPersonCreate withUnitId(String value){return new OrganizationPersonCreate(profileId,subject,jobTitle,JsonField.of(value),managerId);}
    public OrganizationPersonCreate clearUnitId(){return new OrganizationPersonCreate(profileId,subject,jobTitle,JsonField.clear(),managerId);}
    public OrganizationPersonCreate omitUnitId(){return new OrganizationPersonCreate(profileId,subject,jobTitle,null,managerId);}
    public OrganizationPersonCreate withManagerId(String value){return new OrganizationPersonCreate(profileId,subject,jobTitle,unitId,JsonField.of(value));}
    public OrganizationPersonCreate clearManagerId(){return new OrganizationPersonCreate(profileId,subject,jobTitle,unitId,JsonField.clear());}
    public OrganizationPersonCreate omitManagerId(){return new OrganizationPersonCreate(profileId,subject,jobTitle,unitId,null);}
}

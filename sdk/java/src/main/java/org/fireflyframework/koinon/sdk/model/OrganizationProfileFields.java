// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical OrganizationProfileFields contract. */
public record OrganizationProfileFields(
    @JsonProperty("job_title") JsonField<String> jobTitle,
    @JsonProperty("unit_external_key") JsonField<String> unitExternalKey,
    @JsonProperty("manager_external_subject") JsonField<String> managerExternalSubject
) {

    public static OrganizationProfileFields empty(){return new OrganizationProfileFields(null,null,null);}
    public OrganizationProfileFields withJobTitle(String value){return new OrganizationProfileFields(JsonField.of(value),unitExternalKey,managerExternalSubject);}
    public OrganizationProfileFields clearJobTitle(){return new OrganizationProfileFields(JsonField.clear(),unitExternalKey,managerExternalSubject);}
    public OrganizationProfileFields omitJobTitle(){return new OrganizationProfileFields(null,unitExternalKey,managerExternalSubject);}
    public OrganizationProfileFields withUnitExternalKey(String value){return new OrganizationProfileFields(jobTitle,JsonField.of(value),managerExternalSubject);}
    public OrganizationProfileFields clearUnitExternalKey(){return new OrganizationProfileFields(jobTitle,JsonField.clear(),managerExternalSubject);}
    public OrganizationProfileFields omitUnitExternalKey(){return new OrganizationProfileFields(jobTitle,null,managerExternalSubject);}
    public OrganizationProfileFields withManagerExternalSubject(String value){return new OrganizationProfileFields(jobTitle,unitExternalKey,JsonField.of(value));}
    public OrganizationProfileFields clearManagerExternalSubject(){return new OrganizationProfileFields(jobTitle,unitExternalKey,JsonField.clear());}
    public OrganizationProfileFields omitManagerExternalSubject(){return new OrganizationProfileFields(jobTitle,unitExternalKey,null);}
}

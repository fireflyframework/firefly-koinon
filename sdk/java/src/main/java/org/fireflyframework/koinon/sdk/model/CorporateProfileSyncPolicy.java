// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical CorporateProfileSyncPolicy contract. */
public record CorporateProfileSyncPolicy(
    @JsonProperty("interval_seconds") Integer intervalSeconds,
    @JsonProperty("allow_personal_overrides") Boolean allowPersonalOverrides,
    @JsonProperty("name_source") CorporateProfileSyncPolicyNameSource nameSource,
    @JsonProperty("avatar_source") CorporateProfileSyncPolicyNameSource avatarSource,
    @JsonProperty("job_title_source") ProfileFieldSource jobTitleSource,
    @JsonProperty("unit_source") ProfileFieldSource unitSource,
    @JsonProperty("manager_source") ProfileFieldSource managerSource,
    @JsonProperty("google_department") CorporateProfileSyncPolicyGoogleDepartment googleDepartment,
    @JsonProperty("keycloak_attributes") KeycloakProfileAttributes keycloakAttributes
) {

    public static CorporateProfileSyncPolicy empty(){return new CorporateProfileSyncPolicy(null,null,null,null,null,null,null,null,null);}
    public CorporateProfileSyncPolicy withIntervalSeconds(Integer value){return new CorporateProfileSyncPolicy(value,allowPersonalOverrides,nameSource,avatarSource,jobTitleSource,unitSource,managerSource,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withAllowPersonalOverrides(Boolean value){return new CorporateProfileSyncPolicy(intervalSeconds,value,nameSource,avatarSource,jobTitleSource,unitSource,managerSource,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withNameSource(CorporateProfileSyncPolicyNameSource value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,value,avatarSource,jobTitleSource,unitSource,managerSource,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withAvatarSource(CorporateProfileSyncPolicyNameSource value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,nameSource,value,jobTitleSource,unitSource,managerSource,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withJobTitleSource(ProfileFieldSource value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,nameSource,avatarSource,value,unitSource,managerSource,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withUnitSource(ProfileFieldSource value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,nameSource,avatarSource,jobTitleSource,value,managerSource,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withManagerSource(ProfileFieldSource value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,nameSource,avatarSource,jobTitleSource,unitSource,value,googleDepartment,keycloakAttributes);}
    public CorporateProfileSyncPolicy withGoogleDepartment(CorporateProfileSyncPolicyGoogleDepartment value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,nameSource,avatarSource,jobTitleSource,unitSource,managerSource,value,keycloakAttributes);}
    public CorporateProfileSyncPolicy withKeycloakAttributes(KeycloakProfileAttributes value){return new CorporateProfileSyncPolicy(intervalSeconds,allowPersonalOverrides,nameSource,avatarSource,jobTitleSource,unitSource,managerSource,googleDepartment,value);}
}

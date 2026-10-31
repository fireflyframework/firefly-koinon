// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical OrganizationPresentation contract. */
public record OrganizationPresentation(
    @JsonProperty("name_source") ProfilePresentationMode nameSource,
    @JsonProperty("avatar_source") ProfilePresentationMode avatarSource,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("provider_name") String providerName,
    @JsonProperty("status") ProfileSyncStatus status,
    @JsonProperty("last_synced_at") Instant lastSyncedAt,
    @JsonProperty("corporate_department") String corporateDepartment,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("profile_id") String profileId,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("name_mode") ProfilePresentationMode nameMode,
    @JsonProperty("avatar_mode") ProfilePresentationMode avatarMode,
    @JsonProperty("allow_personal_overrides") Boolean allowPersonalOverrides,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("avatar_url") String avatarUrl,
    @JsonProperty("avatar_version") String avatarVersion,
    @JsonProperty("last_attempt_at") Instant lastAttemptAt,
    @JsonProperty("fields") List<CorporateProfileFieldObservation> fields
) {
    public OrganizationPresentation {
        fields=fields==null?null:List.copyOf(fields);
    }

}

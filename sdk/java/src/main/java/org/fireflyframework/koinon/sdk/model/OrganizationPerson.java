// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical OrganizationPerson contract. */
public record OrganizationPerson(
    @JsonProperty("id") String id,
    @JsonProperty("profile_id") String profileId,
    @JsonProperty("display_name") String displayName,
    @JsonProperty("avatar_url") String avatarUrl,
    @JsonProperty("avatar_version") String avatarVersion,
    @JsonProperty("job_title") String jobTitle,
    @JsonProperty("unit") OrganizationUnitSummary unit,
    @JsonProperty("department") OrganizationUnitSummary department,
    @JsonProperty("manager") OrganizationPersonReference manager,
    @JsonProperty("manager_unavailable") Boolean managerUnavailable,
    @JsonProperty("revision") Integer revision,
    @JsonProperty("source") OrganizationPersonSource source,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("provider_name") String providerName,
    @JsonProperty("managed_fields") List<OrganizationManagedField> managedFields,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("updated_at") Instant updatedAt,
    @JsonProperty("observation_status") OrganizationObservationStatus observationStatus
) {
    public OrganizationPerson {
        managedFields=managedFields==null?null:List.copyOf(managedFields);
    }

}

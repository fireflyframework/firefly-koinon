// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CorporatePresentationSummary contract. */
public record CorporatePresentationSummary(
    @JsonProperty("name_source") ProfilePresentationMode nameSource,
    @JsonProperty("avatar_source") ProfilePresentationMode avatarSource,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("provider_name") String providerName,
    @JsonProperty("status") ProfileSyncStatus status,
    @JsonProperty("last_synced_at") Instant lastSyncedAt,
    @JsonProperty("corporate_department") String corporateDepartment
) {

}

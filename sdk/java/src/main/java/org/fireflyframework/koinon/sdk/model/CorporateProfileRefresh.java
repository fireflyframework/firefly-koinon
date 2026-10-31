// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical CorporateProfileRefresh contract. */
public record CorporateProfileRefresh(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("profile_id") String profileId,
    @JsonProperty("status") ProfileSyncStatus status,
    @JsonProperty("snapshot_revision") Integer snapshotRevision,
    @JsonProperty("last_synced_at") Instant lastSyncedAt,
    @JsonProperty("last_attempt_at") Instant lastAttemptAt
) {

}

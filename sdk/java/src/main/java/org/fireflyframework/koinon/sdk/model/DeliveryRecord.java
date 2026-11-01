// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical DeliveryRecord contract. */
public record DeliveryRecord(
    @JsonProperty("id") String id,
    @JsonProperty("kind") DeliveryRecordKind kind,
    @JsonProperty("channel") DeliveryRecordChannel channel,
    @JsonProperty("invitation_id") String invitationId,
    @JsonProperty("membership_id") String membershipId,
    @JsonProperty("recipient_display") String recipientDisplay,
    @JsonProperty("scope_name") String scopeName,
    @JsonProperty("status") DeliveryRecordStatus status,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("last_attempt_at") Instant lastAttemptAt,
    @JsonProperty("next_attempt_at") Instant nextAttemptAt,
    @JsonProperty("attempt_count") Long attemptCount,
    @JsonProperty("failure_code") String failureCode,
    @JsonProperty("safe_explanation") String safeExplanation,
    @JsonProperty("can_retry") Boolean canRetry
) {

}

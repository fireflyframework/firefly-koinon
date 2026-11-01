// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical InvitationDelivery contract. */
public record InvitationDelivery(
    @JsonProperty("id") String id,
    @JsonProperty("status") DeliveryRecordStatus status,
    @JsonProperty("queued_at") Instant queuedAt,
    @JsonProperty("last_attempt_at") Instant lastAttemptAt,
    @JsonProperty("next_attempt_at") Instant nextAttemptAt,
    @JsonProperty("next_resend_at") Instant nextResendAt,
    @JsonProperty("failure_code") String failureCode
) {

}

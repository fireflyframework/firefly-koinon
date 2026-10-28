// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical Share contract. */
public record Share(
    @JsonProperty("id") String id,
    @JsonProperty("title") String title,
    @JsonProperty("revision") String revision,
    @JsonProperty("status") AuthorizedApplicationStatus status,
    @JsonProperty("recipient_policy") ShareRecipientPolicy recipientPolicy,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("revoked_at") Instant revokedAt
) {

}

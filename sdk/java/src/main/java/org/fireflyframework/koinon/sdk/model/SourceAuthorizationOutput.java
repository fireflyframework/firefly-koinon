// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical SourceAuthorizationOutput contract. */
public record SourceAuthorizationOutput(
    @JsonProperty("connection_id") String connectionId,
    @JsonProperty("challenge_id") String challengeId,
    @JsonProperty("authorization_url") String authorizationUrl,
    @JsonProperty("callback_uri") String callbackUri,
    @JsonProperty("expires_at") Instant expiresAt
) {

}

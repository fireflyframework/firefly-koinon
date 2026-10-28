// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical SetupCheck contract. */
public record SetupCheck(
    @JsonProperty("model_id") String modelId,
    @JsonProperty("capability") SetupCheckCapability capability,
    @JsonProperty("supported") Boolean supported,
    @JsonProperty("verified") Boolean verified,
    @JsonProperty("options_key") String optionsKey,
    @JsonProperty("observed_at") Instant observedAt,
    @JsonProperty("id") String id,
    @JsonProperty("status") CheckStatus status,
    @JsonProperty("message") String message
) {

}

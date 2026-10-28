// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical StreamEvent contract. */
public record StreamEvent(
    @JsonProperty("id") String id,
    @JsonProperty("type") String type,
    @JsonProperty("data") ChatEventData data
) {

}

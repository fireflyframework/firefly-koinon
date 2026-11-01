// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical NotificationTarget contract. */
public record NotificationTarget(
    @JsonProperty("kind") NotificationTargetKind kind,
    @JsonProperty("id") String id
) {

}

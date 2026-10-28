// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical ChatRun contract. */
public record ChatRun(
    @JsonProperty("event_cursor") String eventCursor,
    @JsonProperty("run_id") String runId,
    @JsonProperty("message_id") String messageId,
    @JsonProperty("status") MessageStatus status
) {

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical AttachmentObservation contract. */
public record AttachmentObservation(
    @JsonProperty("available") Boolean available,
    @JsonProperty("reason") String reason,
    @JsonProperty("configured") Boolean configured
) {
    public AttachmentObservation { configured = Boolean.TRUE.equals(configured); }
    public AttachmentObservation(Boolean available, String reason) {
        this(available, reason, false);
    }

}

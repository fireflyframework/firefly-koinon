// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AttachmentCapabilities contract. */
public record AttachmentCapabilities(
    @JsonProperty("storage") AttachmentObservation storage,
    @JsonProperty("database") AttachmentObservation database,
    @JsonProperty("extraction") AttachmentObservation extraction,
    @JsonProperty("limits") AttachmentLimits limits,
    @JsonProperty("formats") List<AttachmentFormat> formats,
    @JsonProperty("promotion") AttachmentPromotionRequirements promotion
) {
    public AttachmentCapabilities {
        formats=formats==null?null:List.copyOf(formats);
    }

}

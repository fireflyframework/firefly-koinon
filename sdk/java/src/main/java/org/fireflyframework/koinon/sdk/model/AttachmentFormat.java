// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical AttachmentFormat contract. */
public record AttachmentFormat(
    @JsonProperty("kind") AttachmentFormatKind kind,
    @JsonProperty("media_type") String mediaType,
    @JsonProperty("extensions") List<String> extensions,
    @JsonProperty("extraction") AttachmentObservation extraction
) {
    public AttachmentFormat {
        extensions=extensions==null?null:List.copyOf(extensions);
    }

}

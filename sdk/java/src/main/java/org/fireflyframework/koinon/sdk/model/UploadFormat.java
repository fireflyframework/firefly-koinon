// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical UploadFormat contract. */
public record UploadFormat(
    @JsonProperty("mode") AddKnowledgeMode mode,
    @JsonProperty("extensions") List<String> extensions,
    @JsonProperty("available") Boolean available,
    @JsonProperty("reason") String reason
) {
    public UploadFormat {
        extensions=extensions==null?null:List.copyOf(extensions);
    }

}

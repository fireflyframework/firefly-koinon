// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceDestinationPresentation contract. */
public record SourceDestinationPresentation(
    @JsonProperty("segments") List<SourceDestinationSegment> segments
) {
    public SourceDestinationPresentation {
        segments=segments==null?null:List.copyOf(segments);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SourceRootPresentation contract. */
public record SourceRootPresentation(
    @JsonProperty("name") String name,
    @JsonProperty("relative_path") List<String> relativePath
) {
    public SourceRootPresentation {
        relativePath=relativePath==null?null:List.copyOf(relativePath);
    }

}

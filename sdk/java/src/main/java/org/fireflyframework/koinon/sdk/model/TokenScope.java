// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical TokenScope contract. */
public record TokenScope(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("dependencies") List<String> dependencies
) {
    public TokenScope {
        dependencies=dependencies==null?null:List.copyOf(dependencies);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ProviderCapability contract. */
public record ProviderCapability(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("kind") String kind,
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("available") Boolean available,
    @JsonProperty("reason") String reason,
    @JsonProperty("capabilities") List<String> capabilities
) {
    public ProviderCapability {
        capabilities=capabilities==null?null:List.copyOf(capabilities);
    }

}

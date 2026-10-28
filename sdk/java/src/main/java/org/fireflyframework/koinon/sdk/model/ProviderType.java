// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ProviderType contract. */
public record ProviderType(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("fields") List<FieldSchema> fields
) {
    public ProviderType {
        fields=fields==null?null:List.copyOf(fields);
    }

}

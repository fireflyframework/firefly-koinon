// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical FieldSchema contract. */
public record FieldSchema(
    @JsonProperty("options") List<FieldOption> options,
    @JsonProperty("name") String name,
    @JsonProperty("label") String label,
    @JsonProperty("type") FieldSchemaType type,
    @JsonProperty("required") Boolean required,
    @JsonProperty("write_only") Boolean writeOnly,
    @JsonProperty("default") String defaultValue
) {
    public FieldSchema {
        options=options==null?null:List.copyOf(options);
    }

}

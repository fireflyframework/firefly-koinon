// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical DatasetSchema contract. */
public record DatasetSchema(
    @JsonProperty("tables") List<SchemaTable> tables
) {
    public DatasetSchema {
        tables=tables==null?null:List.copyOf(tables);
    }

}

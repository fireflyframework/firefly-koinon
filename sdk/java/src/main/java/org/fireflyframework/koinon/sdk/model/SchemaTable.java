// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SchemaTable contract. */
public record SchemaTable(
    @JsonProperty("sheet_or_json_path") String sheetOrJsonPath,
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("columns") List<Column> columns
) {
    public SchemaTable {
        columns=columns==null?null:List.copyOf(columns);
    }

}

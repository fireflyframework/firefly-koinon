// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical NativeReadOrigin contract. */
public record NativeReadOrigin(
    @JsonProperty("original_filename") String originalFilename,
    @JsonProperty("sheet_or_json_path") String sheetOrJsonPath,
    @JsonProperty("connection_id") String connectionId,
    @JsonProperty("connection_name") String connectionName,
    @JsonProperty("database") String database,
    @JsonProperty("schema") String schema,
    @JsonProperty("table") String table
) {

}

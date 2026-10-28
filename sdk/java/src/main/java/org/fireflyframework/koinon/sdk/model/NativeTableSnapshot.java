// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical NativeTableSnapshot contract. */
public record NativeTableSnapshot(
    @JsonProperty("table_id") String tableId,
    @JsonProperty("table_name") String tableName,
    @JsonProperty("snapshot_id") String snapshotId
) {

}

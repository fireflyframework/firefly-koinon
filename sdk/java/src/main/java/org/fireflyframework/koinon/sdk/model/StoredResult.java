// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical StoredResult contract. */
public record StoredResult(
    @JsonProperty("query_id") String queryId,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("revision") String revision,
    @JsonProperty("row_count") Long rowCount,
    @JsonProperty("row_cap") Long rowCap,
    @JsonProperty("truncated") Boolean truncated,
    @JsonProperty("completeness") StoredResultCompleteness completeness,
    @JsonProperty("byte_size") Long byteSize,
    @JsonProperty("columns") List<ResultColumn> columns,
    @JsonProperty("snapshot_ids") List<String> snapshotIds,
    @JsonProperty("snapshot_manifest_complete") Boolean snapshotManifestComplete,
    @JsonProperty("expires_at") Instant expiresAt
) {
    public StoredResult {
        columns=columns==null?null:List.copyOf(columns);
        snapshotIds=snapshotIds==null?null:List.copyOf(snapshotIds);
    }

}

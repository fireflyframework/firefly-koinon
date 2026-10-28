// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ContentEffects contract. */
public record ContentEffects(
    @JsonProperty("unchanged") Boolean unchanged,
    @JsonProperty("affected_asset_ids") List<String> affectedAssetIds,
    @JsonProperty("snapshot_id") String snapshotId,
    @JsonProperty("file_id") String fileId,
    @JsonProperty("historical_snapshots_preserved") Boolean historicalSnapshotsPreserved,
    @JsonProperty("citation_rows_preserved") Boolean citationRowsPreserved,
    @JsonProperty("previous_chunk_ids_invalidated") Boolean previousChunkIdsInvalidated
) {
    public ContentEffects {
        affectedAssetIds=affectedAssetIds==null?null:List.copyOf(affectedAssetIds);
    }

}

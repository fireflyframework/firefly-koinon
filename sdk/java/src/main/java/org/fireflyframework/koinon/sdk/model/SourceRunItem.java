// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical SourceRunItem contract. */
public record SourceRunItem(
    @JsonProperty("id") String id,
    @JsonProperty("object_id") String objectId,
    @JsonProperty("generation") Long generation,
    @JsonProperty("remote_version") String remoteVersion,
    @JsonProperty("kind") SourceRunItemKind kind,
    @JsonProperty("name") String name,
    @JsonProperty("relative_path") List<String> relativePath,
    @JsonProperty("status") SourceRunItemStatus status,
    @JsonProperty("error_code") String errorCode,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("attempt_id") String attemptId,
    @JsonProperty("updated_at") Instant updatedAt
) {
    public SourceRunItem {
        relativePath=relativePath==null?null:List.copyOf(relativePath);
    }

}

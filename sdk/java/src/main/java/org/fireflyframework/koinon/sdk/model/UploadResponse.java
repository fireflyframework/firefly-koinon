// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical UploadResponse contract. */
public record UploadResponse(
    @JsonProperty("source") CatalogEntry source,
    @JsonProperty("assets") List<CatalogEntry> assets,
    @JsonProperty("job_id") String jobId
) {
    public UploadResponse {
        assets=assets==null?null:List.copyOf(assets);
    }

}

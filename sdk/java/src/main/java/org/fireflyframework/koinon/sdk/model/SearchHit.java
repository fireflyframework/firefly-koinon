// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;
import java.util.List;



/** Typed canonical SearchHit contract. */
public record SearchHit(
    @JsonProperty("id") String id,
    @JsonProperty("title") String title,
    @JsonProperty("text") String text,
    @JsonProperty("asset_id") String assetId,
    @JsonProperty("source_id") String sourceId,
    @JsonProperty("score") BigDecimal score,
    @JsonProperty("citations") List<Citation> citations
) {
    public SearchHit {
        citations=citations==null?null:List.copyOf(citations);
    }

}

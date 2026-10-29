// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical SearchResponse contract. */
public record SearchResponse(
    @JsonProperty("knowledge_settings_snapshot") OrganizationKnowledgeSnapshot knowledgeSettingsSnapshot,
    @JsonProperty("hits") List<SearchHit> hits,
    @JsonProperty("answer") String answer,
    @JsonProperty("citations") List<Citation> citations
) {
    public SearchResponse {
        hits=hits==null?null:List.copyOf(hits);
        citations=citations==null?null:List.copyOf(citations);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical GlossaryTermRead contract. */
public record GlossaryTermRead(
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("term") String term,
    @JsonProperty("definition") String definition,
    @JsonProperty("synonyms_json") List<String> synonymsJson,
    @JsonProperty("tags_json") List<String> tagsJson,
    @JsonProperty("related_columns_json") List<String> relatedColumnsJson,
    @JsonProperty("related_metrics_json") List<String> relatedMetricsJson,
    @JsonProperty("created_at") String createdAt,
    @JsonProperty("updated_at") String updatedAt
) {
    public GlossaryTermRead {
        synonymsJson=synonymsJson==null?null:List.copyOf(synonymsJson);
        tagsJson=tagsJson==null?null:List.copyOf(tagsJson);
        relatedColumnsJson=relatedColumnsJson==null?null:List.copyOf(relatedColumnsJson);
        relatedMetricsJson=relatedMetricsJson==null?null:List.copyOf(relatedMetricsJson);
    }

}

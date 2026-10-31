// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;



/** Typed canonical BatchQueryOutcome contract. */
public record BatchQueryOutcome(
    @JsonProperty("query_id") String queryId,
    @JsonProperty("execution_status") ExecutionStatus executionStatus,
    @JsonProperty("sql") String sql,
    @JsonProperty("preview") List<JsonNode> preview,
    @JsonProperty("row_count") Integer rowCount,
    @JsonProperty("elapsed_ms") Integer elapsedMs,
    @JsonProperty("truncated") Boolean truncated,
    @JsonProperty("chart_hint") ChartHint chartHint,
    @JsonProperty("explanation") String explanation,
    @JsonProperty("clarification") ClarificationFrame clarification,
    @JsonProperty("grounded_summary") JsonNode groundedSummary,
    @JsonProperty("usage") UsageSummary usage,
    @JsonProperty("snapshot_pins") Map<String,String> snapshotPins,
    @JsonProperty("knowledge_settings_snapshot") OrganizationKnowledgeSnapshot knowledgeSettingsSnapshot
) {
    public BatchQueryOutcome {
        preview=ModelValues.jsonList(preview);
        groundedSummary=ModelValues.json(groundedSummary);
        snapshotPins=snapshotPins==null?null:Map.copyOf(snapshotPins);
    }
    @Override public List<JsonNode> preview(){return ModelValues.jsonList(preview);}
    @Override public JsonNode groundedSummary(){return ModelValues.json(groundedSummary);}
}

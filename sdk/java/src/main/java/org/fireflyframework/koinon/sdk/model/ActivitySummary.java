// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ActivitySummary contract. */
public record ActivitySummary(
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("audience") ActivitySummaryAudience audience,
    @JsonProperty("window") ActivityWindow window,
    @JsonProperty("coverage") ActivityCoverage coverage,
    @JsonProperty("knowledge") KnowledgeActivityCounts knowledge,
    @JsonProperty("top_projects") List<ProjectActivity> topProjects,
    @JsonProperty("daily_activity") List<DailyActivity> dailyActivity,
    @JsonProperty("mcp") McpActivityCounts mcp,
    @JsonProperty("models") ModelActivityCounts models
) {
    public ActivitySummary {
        topProjects=topProjects==null?null:List.copyOf(topProjects);
        dailyActivity=dailyActivity==null?null:List.copyOf(dailyActivity);
    }

}

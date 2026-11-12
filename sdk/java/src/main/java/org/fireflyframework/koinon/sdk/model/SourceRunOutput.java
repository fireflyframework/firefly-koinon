// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.Map;



/** Typed canonical SourceRunOutput contract. */
public record SourceRunOutput(
    @JsonProperty("id") String id,
    @JsonProperty("mapping_id") String mappingId,
    @JsonProperty("policy_revision") Long policyRevision,
    @JsonProperty("control_revision") Long controlRevision,
    @JsonProperty("status") SourceRunOutputStatus status,
    @JsonProperty("stopping") Boolean stopping,
    @JsonProperty("retry_of_run_id") String retryOfRunId,
    @JsonProperty("counters") Map<String,Long> counters,
    @JsonProperty("enumeration_complete") Boolean enumerationComplete,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("finished_at") Instant finishedAt,
    @JsonProperty("can_cancel") Boolean canCancel,
    @JsonProperty("can_retry") Boolean canRetry
) {
    public SourceRunOutput {
        counters=counters==null?null:Map.copyOf(counters);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;



/** Typed canonical GenerationReceipt contract. */
public record GenerationReceipt(
    @JsonProperty("id") String id,
    @JsonProperty("start_sequence") Long startSequence,
    @JsonProperty("agent_id") String agentId,
    @JsonProperty("agent_revision") Long agentRevision,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("provider_revision") Long providerRevision,
    @JsonProperty("provider_kind") ProviderKind providerKind,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("model_class") String modelClass,
    @JsonProperty("api") ModelApi api,
    @JsonProperty("started_at") Instant startedAt,
    @JsonProperty("finished_at") Instant finishedAt,
    @JsonProperty("status") GenerationReceiptStatus status
) {

}

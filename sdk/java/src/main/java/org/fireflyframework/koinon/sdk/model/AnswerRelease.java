// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical AnswerRelease contract. */
public record AnswerRelease(
    @JsonProperty("version") Long version,
    @JsonProperty("policy_version") AnswerReleasePolicyVersion policyVersion,
    @JsonProperty("run_id") String runId,
    @JsonProperty("message_id") String messageId,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("generation_id") String generationId,
    @JsonProperty("publication_sequence") Long publicationSequence,
    @JsonProperty("outcome") AnswerPolicyOutcome outcome,
    @JsonProperty("text_sha256") String textSha256,
    @JsonProperty("citations_sha256") String citationsSha256,
    @JsonProperty("artifacts_sha256") String artifactsSha256,
    @JsonProperty("policy_sha256") String policySha256,
    @JsonProperty("fact_ids") List<String> factIds,
    @JsonProperty("result_pins") List<ResultPin> resultPins,
    @JsonProperty("source_refs") List<SourceReference> sourceRefs,
    @JsonProperty("created_at") Instant createdAt
) {
    public AnswerRelease {
        factIds=factIds==null?null:List.copyOf(factIds);
        resultPins=resultPins==null?null:List.copyOf(resultPins);
        sourceRefs=sourceRefs==null?null:List.copyOf(sourceRefs);
    }

}

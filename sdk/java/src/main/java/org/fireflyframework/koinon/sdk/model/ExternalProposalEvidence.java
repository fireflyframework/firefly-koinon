// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;
import java.util.List;



/** Typed canonical ExternalProposalEvidence contract. */
public record ExternalProposalEvidence(
    @JsonProperty("kind") ExternalFileReviewViewOrigin kind,
    @JsonProperty("text") String text,
    @JsonProperty("sha256") String sha256,
    @JsonProperty("submitted_by") String submittedBy,
    @JsonProperty("credential_id") String credentialId,
    @JsonProperty("application_id") String applicationId,
    @JsonProperty("source_receipt_ids") List<String> sourceReceiptIds,
    @JsonProperty("recorded_at") Instant recordedAt,
    @JsonProperty("authority") ExternalFileReviewViewAuthority authority,
    @JsonProperty("provider") JsonNode provider,
    @JsonProperty("model") JsonNode model
) implements KnowledgeEvidence {
    public ExternalProposalEvidence {
        sourceReceiptIds=sourceReceiptIds==null?null:List.copyOf(sourceReceiptIds);
        provider=ModelValues.json(provider);
        model=ModelValues.json(model);
    }
    @Override public JsonNode provider(){return ModelValues.json(provider);}
    @Override public JsonNode model(){return ModelValues.json(model);}
}

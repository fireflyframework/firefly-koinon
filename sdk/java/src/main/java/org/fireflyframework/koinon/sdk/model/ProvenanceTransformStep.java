// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;



/** Typed canonical ProvenanceTransformStep contract. */
public record ProvenanceTransformStep(
    @JsonProperty("id") String id,
    @JsonProperty("ordinal") Integer ordinal,
    @JsonProperty("kind") String kind,
    @JsonProperty("implementation") String implementation,
    @JsonProperty("implementation_sha256") String implementationSha256,
    @JsonProperty("input_sha256") String inputSha256,
    @JsonProperty("output_sha256") String outputSha256,
    @JsonProperty("parameters") JsonNode parameters,
    @JsonProperty("actor") String actor,
    @JsonProperty("recorded_at") Instant recordedAt
) {
    public ProvenanceTransformStep {
        parameters=ModelValues.json(parameters);
    }
    @Override public JsonNode parameters(){return ModelValues.json(parameters);}
}

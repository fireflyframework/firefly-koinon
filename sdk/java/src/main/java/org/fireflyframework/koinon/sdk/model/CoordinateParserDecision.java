// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;



/** Typed canonical CoordinateParserDecision contract. */
public record CoordinateParserDecision(
    @JsonProperty("name") String name,
    @JsonProperty("value") JsonNode value
) {
    public CoordinateParserDecision {
        value=ModelValues.json(value);
    }
    @Override public JsonNode value(){return ModelValues.json(value);}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical KnowledgeRoles contract. */
public record KnowledgeRoles(
    @JsonProperty("roles") List<KnowledgeRole> roles,
    @JsonProperty("model_options_schema") JsonNode modelOptionsSchema,
    @JsonProperty("providers") List<KnowledgeProvider> providers
) {
    public KnowledgeRoles {
        roles=roles==null?null:List.copyOf(roles);
        modelOptionsSchema=ModelValues.json(modelOptionsSchema);
        providers=providers==null?null:List.copyOf(providers);
    }
    @Override public JsonNode modelOptionsSchema(){return ModelValues.json(modelOptionsSchema);}
}

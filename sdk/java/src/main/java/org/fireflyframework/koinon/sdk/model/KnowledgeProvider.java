// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical KnowledgeProvider contract. */
public record KnowledgeProvider(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("kind") ProviderKind kind,
    @JsonProperty("api") ModelApi api,
    @JsonProperty("model_ids") List<String> modelIds,
    @JsonProperty("enabled") Boolean enabled
) {
    public KnowledgeProvider {
        modelIds=modelIds==null?null:List.copyOf(modelIds);
    }

}

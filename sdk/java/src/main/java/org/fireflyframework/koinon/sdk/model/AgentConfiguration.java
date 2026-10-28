// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical AgentConfiguration contract. */
public record AgentConfiguration(
    @JsonProperty("model_settings") JsonNode modelSettings,
    @JsonProperty("input_modalities") List<AgentConfigurationInputModalities> inputModalities,
    @JsonProperty("input_modality_policy") String inputModalityPolicy,
    @JsonProperty("model_options_supported") List<String> modelOptionsSupported,
    @JsonProperty("api") ModelApi api,
    @JsonProperty("model_class") NativeModelClass modelClass,
    @JsonProperty("model_options") ModelParameters modelOptions,
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("can_run") Boolean canRun,
    @JsonProperty("dependencies") List<ModelConnection> dependencies,
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("description") String description,
    @JsonProperty("provider_id") String providerId,
    @JsonProperty("model_id") String modelId,
    @JsonProperty("tools") List<AgentTool> tools,
    @JsonProperty("scope") KnowledgeScope scope,
    @JsonProperty("instructions") String instructions,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("revision") Long revision,
    @JsonProperty("status") AgentStatus status,
    @JsonProperty("checks") List<SetupCheck> checks
) {
    public AgentConfiguration {
        modelSettings=ModelValues.json(modelSettings);
        inputModalities=inputModalities==null?null:List.copyOf(inputModalities);
        modelOptionsSupported=modelOptionsSupported==null?null:List.copyOf(modelOptionsSupported);
        dependencies=dependencies==null?null:List.copyOf(dependencies);
        tools=tools==null?null:List.copyOf(tools);
        checks=checks==null?null:List.copyOf(checks);
    }
    @Override public JsonNode modelSettings(){return ModelValues.json(modelSettings);}
}

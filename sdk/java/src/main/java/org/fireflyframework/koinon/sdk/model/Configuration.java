// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;



/** Typed canonical Configuration contract. */
public record Configuration(
    @JsonProperty("framework_providers") List<ProviderSupport> frameworkProviders,
    @JsonProperty("model_options_schema") JsonNode modelOptionsSchema,
    @JsonProperty("deployment") DeploymentConfiguration deployment,
    @JsonProperty("providers") List<ModelProvider> providers,
    @JsonProperty("provider_types") List<ProviderType> providerTypes,
    @JsonProperty("connections") List<ModelConnection> connections,
    @JsonProperty("checks") List<SetupCheck> checks
) {
    public Configuration {
        frameworkProviders=frameworkProviders==null?null:List.copyOf(frameworkProviders);
        modelOptionsSchema=ModelValues.json(modelOptionsSchema);
        providers=providers==null?null:List.copyOf(providers);
        providerTypes=providerTypes==null?null:List.copyOf(providerTypes);
        connections=connections==null?null:List.copyOf(connections);
        checks=checks==null?null:List.copyOf(checks);
    }
    @Override public JsonNode modelOptionsSchema(){return ModelValues.json(modelOptionsSchema);}
}

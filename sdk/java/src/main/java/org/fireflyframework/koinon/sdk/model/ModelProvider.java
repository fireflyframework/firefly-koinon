// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical ModelProvider contract. */
public record ModelProvider(
    @JsonProperty("native_adapter") NativeAdapter nativeAdapter,
    @JsonProperty("api") ModelApi api,
    @JsonProperty("model_class") NativeModelClass modelClass,
    @JsonProperty("configured") Boolean configured,
    @JsonProperty("connected") Boolean connected,
    @JsonProperty("discovered") Boolean discovered,
    @JsonProperty("model_capabilities") List<ModelCapability> modelCapabilities,
    @JsonProperty("configuration_ownership") ModelProviderConfigurationOwnership configurationOwnership,
    @JsonProperty("credential_ownership") ModelProviderCredentialOwnership credentialOwnership,
    @JsonProperty("ambient_credentials") Boolean ambientCredentials,
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("kind") ProviderKind kind,
    @JsonProperty("base_url") String baseUrl,
    @JsonProperty("model_ids") List<String> modelIds,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("revision") Long revision,
    @JsonProperty("secret_configured") Boolean secretConfigured,
    @JsonProperty("validated") Boolean validated,
    @JsonProperty("checks") List<SetupCheck> checks
) {
    public ModelProvider {
        modelCapabilities=modelCapabilities==null?null:List.copyOf(modelCapabilities);
        modelIds=modelIds==null?null:List.copyOf(modelIds);
        checks=checks==null?null:List.copyOf(checks);
    }

}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpOAuthClientReadiness contract. */
public record McpOAuthClientReadiness(
    @JsonProperty("ready") Boolean ready,
    @JsonProperty("endpoint_enabled") Boolean endpointEnabled,
    @JsonProperty("oauth_enabled") Boolean oauthEnabled,
    @JsonProperty("encryption_configured") Boolean encryptionConfigured,
    @JsonProperty("missing_configuration") List<McpOAuthClientReadinessMissingConfiguration> missingConfiguration,
    @JsonProperty("static_clients_read_only") Boolean staticClientsReadOnly
) {
    public McpOAuthClientReadiness {
        missingConfiguration=missingConfiguration==null?null:List.copyOf(missingConfiguration);
    }

}

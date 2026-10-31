// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpConnectionDescriptor contract. */
public record McpConnectionDescriptor(
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("local_only") Boolean localOnly,
    @JsonProperty("endpoint") String endpoint,
    @JsonProperty("transport") McpConnectionDescriptorTransport transport,
    @JsonProperty("authentication") List<McpConnectionDescriptorAuthentication> authentication,
    @JsonProperty("clients") List<McpRegisteredClient> clients,
    @JsonProperty("oauth_enabled") Boolean oauthEnabled,
    @JsonProperty("oauth_registration") McpConnectionDescriptorOauthRegistration oauthRegistration,
    @JsonProperty("supported_scopes") List<String> supportedScopes,
    @JsonProperty("tools") List<McpToolCapability> tools,
    @JsonProperty("review") McpReviewSupport review,
    @JsonProperty("client_acceptance") McpConnectionDescriptorClientAcceptance clientAcceptance
) {
    public McpConnectionDescriptor {
        authentication=authentication==null?null:List.copyOf(authentication);
        clients=clients==null?null:List.copyOf(clients);
        supportedScopes=supportedScopes==null?null:List.copyOf(supportedScopes);
        tools=tools==null?null:List.copyOf(tools);
    }

}

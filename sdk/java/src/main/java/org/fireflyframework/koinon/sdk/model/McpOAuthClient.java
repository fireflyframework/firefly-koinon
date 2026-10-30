// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical McpOAuthClient contract. */
public record McpOAuthClient(
    @JsonProperty("name") String name,
    @JsonProperty("redirect_uris") List<String> redirectUris,
    @JsonProperty("scopes") List<McpOAuthScope> scopes,
    @JsonProperty("id") String id,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("client_id") String clientId,
    @JsonProperty("client_type") McpRegisteredClientClientAuth clientType,
    @JsonProperty("enabled") Boolean enabled,
    @JsonProperty("revision") Long revision,
    @JsonProperty("created_at") Instant createdAt,
    @JsonProperty("updated_at") Instant updatedAt,
    @JsonProperty("created_by") String createdBy,
    @JsonProperty("updated_by") String updatedBy
) {
    public McpOAuthClient {
        redirectUris=redirectUris==null?null:List.copyOf(redirectUris);
        scopes=scopes==null?null:List.copyOf(scopes);
    }

}

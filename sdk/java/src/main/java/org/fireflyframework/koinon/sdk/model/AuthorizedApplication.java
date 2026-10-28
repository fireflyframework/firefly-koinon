// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical AuthorizedApplication contract. */
public record AuthorizedApplication(
    @JsonProperty("id") String id,
    @JsonProperty("client_id") String clientId,
    @JsonProperty("name") String name,
    @JsonProperty("resource") String resource,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("tenant_name") String tenantName,
    @JsonProperty("workspace_id") String workspaceId,
    @JsonProperty("workspace_name") String workspaceName,
    @JsonProperty("scopes") List<String> scopes,
    @JsonProperty("status") AuthorizedApplicationStatus status,
    @JsonProperty("connected_at") Instant connectedAt,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("last_used_at") Instant lastUsedAt,
    @JsonProperty("revoked_at") Instant revokedAt
) {
    public AuthorizedApplication {
        scopes=scopes==null?null:List.copyOf(scopes);
    }

}

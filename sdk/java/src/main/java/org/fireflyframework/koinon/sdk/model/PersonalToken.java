// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical PersonalToken contract. */
public record PersonalToken(
    @JsonProperty("id") String id,
    @JsonProperty("name") String name,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("prefix") String prefix,
    @JsonProperty("scopes") List<String> scopes,
    @JsonProperty("workspace_ids") List<String> workspaceIds,
    @JsonProperty("asset_ids") List<String> assetIds,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("revoked_at") Instant revokedAt,
    @JsonProperty("last_used_at") Instant lastUsedAt,
    @JsonProperty("created_at") Instant createdAt
) {
    public PersonalToken {
        scopes=scopes==null?null:List.copyOf(scopes);
        workspaceIds=workspaceIds==null?null:List.copyOf(workspaceIds);
        assetIds=assetIds==null?null:List.copyOf(assetIds);
    }

}

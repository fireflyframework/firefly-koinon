// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;



/** Typed canonical TokenInput contract. */
public record TokenInput(
    @JsonProperty("name") String name,
    @JsonProperty("tenant_id") String tenantId,
    @JsonProperty("scopes") List<String> scopes,
    @JsonProperty("expires_at") Instant expiresAt,
    @JsonProperty("workspace_ids") JsonField<List<String>> workspaceIds,
    @JsonProperty("asset_ids") JsonField<List<String>> assetIds
) {
    public TokenInput {
        scopes=scopes==null?null:List.copyOf(scopes);
    }

    public static TokenInput empty(){return new TokenInput(null,null,null,null,null,null);}
    public TokenInput withName(String value){return new TokenInput(value,tenantId,scopes,expiresAt,workspaceIds,assetIds);}
    public TokenInput withTenantId(String value){return new TokenInput(name,value,scopes,expiresAt,workspaceIds,assetIds);}
    public TokenInput withScopes(List<String> value){return new TokenInput(name,tenantId,value,expiresAt,workspaceIds,assetIds);}
    public TokenInput withExpiresAt(Instant value){return new TokenInput(name,tenantId,scopes,value,workspaceIds,assetIds);}
    public TokenInput withWorkspaceIds(List<String> value){return new TokenInput(name,tenantId,scopes,expiresAt,JsonField.of(value),assetIds);}
    public TokenInput clearWorkspaceIds(){return new TokenInput(name,tenantId,scopes,expiresAt,JsonField.clear(),assetIds);}
    public TokenInput omitWorkspaceIds(){return new TokenInput(name,tenantId,scopes,expiresAt,null,assetIds);}
    public TokenInput withAssetIds(List<String> value){return new TokenInput(name,tenantId,scopes,expiresAt,workspaceIds,JsonField.of(value));}
    public TokenInput clearAssetIds(){return new TokenInput(name,tenantId,scopes,expiresAt,workspaceIds,JsonField.clear());}
    public TokenInput omitAssetIds(){return new TokenInput(name,tenantId,scopes,expiresAt,workspaceIds,null);}
}

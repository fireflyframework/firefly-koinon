// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpOAuthClientValues contract. */
public record McpOAuthClientValues(
    @JsonProperty("name") String name,
    @JsonProperty("redirect_uris") List<String> redirectUris,
    @JsonProperty("scopes") List<McpOAuthScope> scopes
) {
    public McpOAuthClientValues {
        redirectUris=redirectUris==null?null:List.copyOf(redirectUris);
        scopes=scopes==null?null:List.copyOf(scopes);
    }

    public static McpOAuthClientValues empty(){return new McpOAuthClientValues(null,null,null);}
    public McpOAuthClientValues withName(String value){return new McpOAuthClientValues(value,redirectUris,scopes);}
    public McpOAuthClientValues withRedirectUris(List<String> value){return new McpOAuthClientValues(name,value,scopes);}
    public McpOAuthClientValues withScopes(List<McpOAuthScope> value){return new McpOAuthClientValues(name,redirectUris,value);}
}

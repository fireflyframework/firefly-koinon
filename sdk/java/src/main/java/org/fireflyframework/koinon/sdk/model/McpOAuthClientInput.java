// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpOAuthClientInput contract. */
public record McpOAuthClientInput(
    @JsonProperty("name") String name,
    @JsonProperty("redirect_uris") List<String> redirectUris,
    @JsonProperty("scopes") List<McpOAuthScope> scopes,
    @JsonProperty("client_type") McpRegisteredClientClientAuth clientType
) {
    public McpOAuthClientInput {
        redirectUris=redirectUris==null?null:List.copyOf(redirectUris);
        scopes=scopes==null?null:List.copyOf(scopes);
    }

    public static McpOAuthClientInput empty(){return new McpOAuthClientInput(null,null,null,null);}
    public McpOAuthClientInput withName(String value){return new McpOAuthClientInput(value,redirectUris,scopes,clientType);}
    public McpOAuthClientInput withRedirectUris(List<String> value){return new McpOAuthClientInput(name,value,scopes,clientType);}
    public McpOAuthClientInput withScopes(List<McpOAuthScope> value){return new McpOAuthClientInput(name,redirectUris,value,clientType);}
    public McpOAuthClientInput withClientType(McpRegisteredClientClientAuth value){return new McpOAuthClientInput(name,redirectUris,scopes,value);}
}

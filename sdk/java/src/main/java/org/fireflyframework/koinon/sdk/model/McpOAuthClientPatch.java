// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;



/** Typed canonical McpOAuthClientPatch contract. */
public record McpOAuthClientPatch(
    @JsonProperty("expected_revision") Integer expectedRevision,
    @JsonProperty("name") JsonField<String> name,
    @JsonProperty("redirect_uris") JsonField<List<String>> redirectUris,
    @JsonProperty("scopes") JsonField<List<McpOAuthScope>> scopes,
    @JsonProperty("enabled") JsonField<Boolean> enabled
) {

    public static McpOAuthClientPatch empty(){return new McpOAuthClientPatch(null,null,null,null,null);}
    public McpOAuthClientPatch withExpectedRevision(Integer value){return new McpOAuthClientPatch(value,name,redirectUris,scopes,enabled);}
    public McpOAuthClientPatch withName(String value){return new McpOAuthClientPatch(expectedRevision,JsonField.of(value),redirectUris,scopes,enabled);}
    public McpOAuthClientPatch clearName(){return new McpOAuthClientPatch(expectedRevision,JsonField.clear(),redirectUris,scopes,enabled);}
    public McpOAuthClientPatch omitName(){return new McpOAuthClientPatch(expectedRevision,null,redirectUris,scopes,enabled);}
    public McpOAuthClientPatch withRedirectUris(List<String> value){return new McpOAuthClientPatch(expectedRevision,name,JsonField.of(value),scopes,enabled);}
    public McpOAuthClientPatch clearRedirectUris(){return new McpOAuthClientPatch(expectedRevision,name,JsonField.clear(),scopes,enabled);}
    public McpOAuthClientPatch omitRedirectUris(){return new McpOAuthClientPatch(expectedRevision,name,null,scopes,enabled);}
    public McpOAuthClientPatch withScopes(List<McpOAuthScope> value){return new McpOAuthClientPatch(expectedRevision,name,redirectUris,JsonField.of(value),enabled);}
    public McpOAuthClientPatch clearScopes(){return new McpOAuthClientPatch(expectedRevision,name,redirectUris,JsonField.clear(),enabled);}
    public McpOAuthClientPatch omitScopes(){return new McpOAuthClientPatch(expectedRevision,name,redirectUris,null,enabled);}
    public McpOAuthClientPatch withEnabled(Boolean value){return new McpOAuthClientPatch(expectedRevision,name,redirectUris,scopes,JsonField.of(value));}
    public McpOAuthClientPatch clearEnabled(){return new McpOAuthClientPatch(expectedRevision,name,redirectUris,scopes,JsonField.clear());}
    public McpOAuthClientPatch omitEnabled(){return new McpOAuthClientPatch(expectedRevision,name,redirectUris,scopes,null);}
}

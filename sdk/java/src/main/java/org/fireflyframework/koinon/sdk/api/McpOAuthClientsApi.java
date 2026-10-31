// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class McpOAuthClientsApi {
private final Transport transport; private final String prefix;
public McpOAuthClientsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public McpOAuthClientReadiness readiness(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/mcp/oauth-clients/readiness",null,options,transport.type(McpOAuthClientReadiness.class));}
public McpOAuthClientReadiness readiness(){return readiness(RequestOptions.defaults());}
public CompletableFuture<McpOAuthClientReadiness> readinessAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/mcp/oauth-clients/readiness",null,options,transport.type(McpOAuthClientReadiness.class));}
public CompletableFuture<McpOAuthClientReadiness> readinessAsync(){return readinessAsync(RequestOptions.defaults());}
public McpOAuthClientPage list(McpOAuthClientFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/mcp/oauth-clients",null,options,transport.type(McpOAuthClientPage.class));}
public McpOAuthClientPage list(McpOAuthClientFilter filter){return list(filter,RequestOptions.defaults());}
public McpOAuthClientPage list(){return list(McpOAuthClientFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<McpOAuthClientPage> listAsync(McpOAuthClientFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/mcp/oauth-clients",null,options,transport.type(McpOAuthClientPage.class));}
public CompletableFuture<McpOAuthClientPage> listAsync(McpOAuthClientFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<McpOAuthClientPage> listAsync(){return listAsync(McpOAuthClientFilter.empty(),RequestOptions.defaults());}
public McpOAuthClientCredential create(McpOAuthClientInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/mcp/oauth-clients",input,options,transport.type(McpOAuthClientCredential.class));}
public McpOAuthClientCredential create(McpOAuthClientInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<McpOAuthClientCredential> createAsync(McpOAuthClientInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/mcp/oauth-clients",input,options,transport.type(McpOAuthClientCredential.class));}
public CompletableFuture<McpOAuthClientCredential> createAsync(McpOAuthClientInput input){return createAsync(input,RequestOptions.defaults());}
public McpOAuthClient get(String clientId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/mcp/oauth-clients/"+Transport.id(clientId),null,options,transport.type(McpOAuthClient.class));}
public McpOAuthClient get(String clientId){return get(clientId,RequestOptions.defaults());}
public CompletableFuture<McpOAuthClient> getAsync(String clientId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/mcp/oauth-clients/"+Transport.id(clientId),null,options,transport.type(McpOAuthClient.class));}
public CompletableFuture<McpOAuthClient> getAsync(String clientId){return getAsync(clientId,RequestOptions.defaults());}
public McpOAuthClient update(String clientId,McpOAuthClientPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/mcp/oauth-clients/"+Transport.id(clientId),input,options,transport.type(McpOAuthClient.class));}
public McpOAuthClient update(String clientId,McpOAuthClientPatch input){return update(clientId,input,RequestOptions.defaults());}
public CompletableFuture<McpOAuthClient> updateAsync(String clientId,McpOAuthClientPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/mcp/oauth-clients/"+Transport.id(clientId),input,options,transport.type(McpOAuthClient.class));}
public CompletableFuture<McpOAuthClient> updateAsync(String clientId,McpOAuthClientPatch input){return updateAsync(clientId,input,RequestOptions.defaults());}
public McpOAuthClientCredential rotateSecret(String clientId,McpOAuthClientRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/mcp/oauth-clients/"+Transport.id(clientId)+"/rotate-secret",input,options,transport.type(McpOAuthClientCredential.class));}
public McpOAuthClientCredential rotateSecret(String clientId,McpOAuthClientRevision input){return rotateSecret(clientId,input,RequestOptions.defaults());}
public CompletableFuture<McpOAuthClientCredential> rotateSecretAsync(String clientId,McpOAuthClientRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/mcp/oauth-clients/"+Transport.id(clientId)+"/rotate-secret",input,options,transport.type(McpOAuthClientCredential.class));}
public CompletableFuture<McpOAuthClientCredential> rotateSecretAsync(String clientId,McpOAuthClientRevision input){return rotateSecretAsync(clientId,input,RequestOptions.defaults());}
}

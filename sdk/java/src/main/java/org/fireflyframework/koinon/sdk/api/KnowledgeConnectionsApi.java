// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class KnowledgeConnectionsApi {
private final Transport transport; private final String prefix;
public KnowledgeConnectionsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public KnowledgeRoles roles(WorkspaceFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge-roles",null,options,transport.type(KnowledgeRoles.class));}
public KnowledgeRoles roles(WorkspaceFilter filter){return roles(filter,RequestOptions.defaults());}
public KnowledgeRoles roles(){return roles(WorkspaceFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<KnowledgeRoles> rolesAsync(WorkspaceFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge-roles",null,options,transport.type(KnowledgeRoles.class));}
public CompletableFuture<KnowledgeRoles> rolesAsync(WorkspaceFilter filter){return rolesAsync(filter,RequestOptions.defaults());}
public CompletableFuture<KnowledgeRoles> rolesAsync(){return rolesAsync(WorkspaceFilter.empty(),RequestOptions.defaults());}
public Page<KnowledgeConnection> list(WorkspaceFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge-connections",null,options,transport.pageType(KnowledgeConnection.class));}
public Page<KnowledgeConnection> list(WorkspaceFilter filter){return list(filter,RequestOptions.defaults());}
public Page<KnowledgeConnection> list(){return list(WorkspaceFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<KnowledgeConnection>> listAsync(WorkspaceFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge-connections",null,options,transport.pageType(KnowledgeConnection.class));}
public CompletableFuture<Page<KnowledgeConnection>> listAsync(WorkspaceFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<KnowledgeConnection>> listAsync(){return listAsync(WorkspaceFilter.empty(),RequestOptions.defaults());}
public KnowledgeConnection create(KnowledgeConnectionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-connections",input,options,transport.type(KnowledgeConnection.class));}
public KnowledgeConnection create(KnowledgeConnectionInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeConnection> createAsync(KnowledgeConnectionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-connections",input,options,transport.type(KnowledgeConnection.class));}
public CompletableFuture<KnowledgeConnection> createAsync(KnowledgeConnectionInput input){return createAsync(input,RequestOptions.defaults());}
public KnowledgeConnection update(String connectionId,KnowledgeConnectionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PUT",prefix+"/knowledge-connections/"+Transport.id(connectionId),input,options,transport.type(KnowledgeConnection.class));}
public KnowledgeConnection update(String connectionId,KnowledgeConnectionInput input){return update(connectionId,input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeConnection> updateAsync(String connectionId,KnowledgeConnectionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PUT",prefix+"/knowledge-connections/"+Transport.id(connectionId),input,options,transport.type(KnowledgeConnection.class));}
public CompletableFuture<KnowledgeConnection> updateAsync(String connectionId,KnowledgeConnectionInput input){return updateAsync(connectionId,input,RequestOptions.defaults());}
public KnowledgeConnection get(String connectionId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge-connections/"+Transport.id(connectionId),null,options,transport.type(KnowledgeConnection.class));}
public KnowledgeConnection get(String connectionId){return get(connectionId,RequestOptions.defaults());}
public CompletableFuture<KnowledgeConnection> getAsync(String connectionId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge-connections/"+Transport.id(connectionId),null,options,transport.type(KnowledgeConnection.class));}
public CompletableFuture<KnowledgeConnection> getAsync(String connectionId){return getAsync(connectionId,RequestOptions.defaults());}
public Deleted remove(String connectionId,ConnectionDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("DELETE",prefix+"/knowledge-connections/"+Transport.id(connectionId),null,options,transport.type(Deleted.class));}
public Deleted remove(String connectionId,ConnectionDeleteFilter filter){return remove(connectionId,filter,RequestOptions.defaults());}
public CompletableFuture<Deleted> removeAsync(String connectionId,ConnectionDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("DELETE",prefix+"/knowledge-connections/"+Transport.id(connectionId),null,options,transport.type(Deleted.class));}
public CompletableFuture<Deleted> removeAsync(String connectionId,ConnectionDeleteFilter filter){return removeAsync(connectionId,filter,RequestOptions.defaults());}
}

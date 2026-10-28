// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class KnowledgeItemsApi {
private final Transport transport; private final String prefix;
public KnowledgeItemsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public KnowledgeItemPage list(KnowledgeItemFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge-items",null,options,transport.type(KnowledgeItemPage.class));}
public KnowledgeItemPage list(KnowledgeItemFilter filter){return list(filter,RequestOptions.defaults());}
public KnowledgeItemPage list(){return list(KnowledgeItemFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<KnowledgeItemPage> listAsync(KnowledgeItemFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge-items",null,options,transport.type(KnowledgeItemPage.class));}
public CompletableFuture<KnowledgeItemPage> listAsync(KnowledgeItemFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<KnowledgeItemPage> listAsync(){return listAsync(KnowledgeItemFilter.empty(),RequestOptions.defaults());}
public KnowledgeItemView get(String itemId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge-items/"+Transport.id(itemId),null,options,transport.type(KnowledgeItemView.class));}
public KnowledgeItemView get(String itemId){return get(itemId,RequestOptions.defaults());}
public CompletableFuture<KnowledgeItemView> getAsync(String itemId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge-items/"+Transport.id(itemId),null,options,transport.type(KnowledgeItemView.class));}
public CompletableFuture<KnowledgeItemView> getAsync(String itemId){return getAsync(itemId,RequestOptions.defaults());}
public KnowledgeItemView version(String itemId,Long version,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(version);return transport.json("GET",prefix+"/knowledge-items/"+Transport.id(itemId)+"/versions/"+Transport.id(String.valueOf(version)),null,options,transport.type(KnowledgeItemView.class));}
public KnowledgeItemView version(String itemId,Long version){return version(itemId,version,RequestOptions.defaults());}
public CompletableFuture<KnowledgeItemView> versionAsync(String itemId,Long version,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(version);return transport.jsonAsync("GET",prefix+"/knowledge-items/"+Transport.id(itemId)+"/versions/"+Transport.id(String.valueOf(version)),null,options,transport.type(KnowledgeItemView.class));}
public CompletableFuture<KnowledgeItemView> versionAsync(String itemId,Long version){return versionAsync(itemId,version,RequestOptions.defaults());}
}

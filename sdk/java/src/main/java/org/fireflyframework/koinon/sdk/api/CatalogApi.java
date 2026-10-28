// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class CatalogApi {
private final Transport transport; private final String prefix;
public CatalogApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<CatalogEntry> list(CatalogFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/catalog",null,options,transport.pageType(CatalogEntry.class));}
public Page<CatalogEntry> list(CatalogFilter filter){return list(filter,RequestOptions.defaults());}
public Page<CatalogEntry> list(){return list(CatalogFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<CatalogEntry>> listAsync(CatalogFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/catalog",null,options,transport.pageType(CatalogEntry.class));}
public CompletableFuture<Page<CatalogEntry>> listAsync(CatalogFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<CatalogEntry>> listAsync(){return listAsync(CatalogFilter.empty(),RequestOptions.defaults());}
public CatalogEntry create(CatalogCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/catalog",input,options,transport.type(CatalogEntry.class));}
public CatalogEntry create(CatalogCreate input){return create(input,RequestOptions.defaults());}
public CompletableFuture<CatalogEntry> createAsync(CatalogCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/catalog",input,options,transport.type(CatalogEntry.class));}
public CompletableFuture<CatalogEntry> createAsync(CatalogCreate input){return createAsync(input,RequestOptions.defaults());}
public CatalogEntry get(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/catalog/"+Transport.id(entryId),null,options,transport.type(CatalogEntry.class));}
public CatalogEntry get(String entryId){return get(entryId,RequestOptions.defaults());}
public CompletableFuture<CatalogEntry> getAsync(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/catalog/"+Transport.id(entryId),null,options,transport.type(CatalogEntry.class));}
public CompletableFuture<CatalogEntry> getAsync(String entryId){return getAsync(entryId,RequestOptions.defaults());}
public CatalogEntry update(String entryId,CatalogUpdate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/catalog/"+Transport.id(entryId),input,options,transport.type(CatalogEntry.class));}
public CatalogEntry update(String entryId,CatalogUpdate input){return update(entryId,input,RequestOptions.defaults());}
public CompletableFuture<CatalogEntry> updateAsync(String entryId,CatalogUpdate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/catalog/"+Transport.id(entryId),input,options,transport.type(CatalogEntry.class));}
public CompletableFuture<CatalogEntry> updateAsync(String entryId,CatalogUpdate input){return updateAsync(entryId,input,RequestOptions.defaults());}
public CatalogEntry archive(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/catalog/"+Transport.id(entryId)+"/archive",null,options,transport.type(CatalogEntry.class));}
public CatalogEntry archive(String entryId){return archive(entryId,RequestOptions.defaults());}
public CompletableFuture<CatalogEntry> archiveAsync(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/catalog/"+Transport.id(entryId)+"/archive",null,options,transport.type(CatalogEntry.class));}
public CompletableFuture<CatalogEntry> archiveAsync(String entryId){return archiveAsync(entryId,RequestOptions.defaults());}
public CatalogEntry restore(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/catalog/"+Transport.id(entryId)+"/restore",null,options,transport.type(CatalogEntry.class));}
public CatalogEntry restore(String entryId){return restore(entryId,RequestOptions.defaults());}
public CompletableFuture<CatalogEntry> restoreAsync(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/catalog/"+Transport.id(entryId)+"/restore",null,options,transport.type(CatalogEntry.class));}
public CompletableFuture<CatalogEntry> restoreAsync(String entryId){return restoreAsync(entryId,RequestOptions.defaults());}
public Void delete(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/catalog/"+Transport.id(entryId),null,options,transport.type(Void.class));}
public Void delete(String entryId){return delete(entryId,RequestOptions.defaults());}
public CompletableFuture<Void> deleteAsync(String entryId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/catalog/"+Transport.id(entryId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> deleteAsync(String entryId){return deleteAsync(entryId,RequestOptions.defaults());}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class QueryBatchesApi {
private final Transport transport; private final String prefix;
public QueryBatchesApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public QueryBatchCapabilities capabilities(QueryBatchScope filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/query-batch-capabilities",null,options,transport.type(QueryBatchCapabilities.class));}
public QueryBatchCapabilities capabilities(QueryBatchScope filter){return capabilities(filter,RequestOptions.defaults());}
public CompletableFuture<QueryBatchCapabilities> capabilitiesAsync(QueryBatchScope filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/query-batch-capabilities",null,options,transport.type(QueryBatchCapabilities.class));}
public CompletableFuture<QueryBatchCapabilities> capabilitiesAsync(QueryBatchScope filter){return capabilitiesAsync(filter,RequestOptions.defaults());}
public QueryBatchView create(QueryBatchCreate input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/queries/batches",input,options,transport.type(QueryBatchView.class));}
public QueryBatchView create(QueryBatchCreate input,String idempotencyKey){return create(input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<QueryBatchView> createAsync(QueryBatchCreate input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/queries/batches",input,options,transport.type(QueryBatchView.class));}
public CompletableFuture<QueryBatchView> createAsync(QueryBatchCreate input,String idempotencyKey){return createAsync(input,idempotencyKey,RequestOptions.defaults());}
public QueryBatchPage list(QueryBatchFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/queries/batches",null,options,transport.type(QueryBatchPage.class));}
public QueryBatchPage list(QueryBatchFilter filter){return list(filter,RequestOptions.defaults());}
public QueryBatchPage list(){return list(QueryBatchFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<QueryBatchPage> listAsync(QueryBatchFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/queries/batches",null,options,transport.type(QueryBatchPage.class));}
public CompletableFuture<QueryBatchPage> listAsync(QueryBatchFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<QueryBatchPage> listAsync(){return listAsync(QueryBatchFilter.empty(),RequestOptions.defaults());}
public QueryBatchView get(String batchId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/queries/batches/"+Transport.id(batchId),null,options,transport.type(QueryBatchView.class));}
public QueryBatchView get(String batchId){return get(batchId,RequestOptions.defaults());}
public CompletableFuture<QueryBatchView> getAsync(String batchId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/queries/batches/"+Transport.id(batchId),null,options,transport.type(QueryBatchView.class));}
public CompletableFuture<QueryBatchView> getAsync(String batchId){return getAsync(batchId,RequestOptions.defaults());}
public QueryBatchItemPage items(String batchId,QueryBatchFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/queries/batches/"+Transport.id(batchId)+"/items",null,options,transport.type(QueryBatchItemPage.class));}
public QueryBatchItemPage items(String batchId,QueryBatchFilter filter){return items(batchId,filter,RequestOptions.defaults());}
public QueryBatchItemPage items(String batchId){return items(batchId,QueryBatchFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<QueryBatchItemPage> itemsAsync(String batchId,QueryBatchFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/queries/batches/"+Transport.id(batchId)+"/items",null,options,transport.type(QueryBatchItemPage.class));}
public CompletableFuture<QueryBatchItemPage> itemsAsync(String batchId,QueryBatchFilter filter){return itemsAsync(batchId,filter,RequestOptions.defaults());}
public CompletableFuture<QueryBatchItemPage> itemsAsync(String batchId){return itemsAsync(batchId,QueryBatchFilter.empty(),RequestOptions.defaults());}
public QueryBatchResult result(String batchId,String itemId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/queries/batches/"+Transport.id(batchId)+"/items/"+Transport.id(itemId)+"/result",null,options,transport.type(QueryBatchResult.class));}
public QueryBatchResult result(String batchId,String itemId){return result(batchId,itemId,RequestOptions.defaults());}
public CompletableFuture<QueryBatchResult> resultAsync(String batchId,String itemId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/queries/batches/"+Transport.id(batchId)+"/items/"+Transport.id(itemId)+"/result",null,options,transport.type(QueryBatchResult.class));}
public CompletableFuture<QueryBatchResult> resultAsync(String batchId,String itemId){return resultAsync(batchId,itemId,RequestOptions.defaults());}
public QueryBatchCancellation cancel(String batchId,QueryBatchAction input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/queries/batches/"+Transport.id(batchId)+"/cancel",input,options,transport.type(QueryBatchCancellation.class));}
public QueryBatchCancellation cancel(String batchId,QueryBatchAction input,String idempotencyKey){return cancel(batchId,input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<QueryBatchCancellation> cancelAsync(String batchId,QueryBatchAction input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/queries/batches/"+Transport.id(batchId)+"/cancel",input,options,transport.type(QueryBatchCancellation.class));}
public CompletableFuture<QueryBatchCancellation> cancelAsync(String batchId,QueryBatchAction input,String idempotencyKey){return cancelAsync(batchId,input,idempotencyKey,RequestOptions.defaults());}
public QueryBatchView reconcile(String batchId,String itemId,QueryBatchAction input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/queries/batches/"+Transport.id(batchId)+"/items/"+Transport.id(itemId)+"/reconcile",input,options,transport.type(QueryBatchView.class));}
public QueryBatchView reconcile(String batchId,String itemId,QueryBatchAction input,String idempotencyKey){return reconcile(batchId,itemId,input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<QueryBatchView> reconcileAsync(String batchId,String itemId,QueryBatchAction input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/queries/batches/"+Transport.id(batchId)+"/items/"+Transport.id(itemId)+"/reconcile",input,options,transport.type(QueryBatchView.class));}
public CompletableFuture<QueryBatchView> reconcileAsync(String batchId,String itemId,QueryBatchAction input,String idempotencyKey){return reconcileAsync(batchId,itemId,input,idempotencyKey,RequestOptions.defaults());}
}

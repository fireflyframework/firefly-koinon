// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class KnowledgeIndexesApi {
private final Transport transport; private final String prefix;
public KnowledgeIndexesApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public IndexPage list(IndexFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge-indexes",null,options,transport.type(IndexPage.class));}
public IndexPage list(IndexFilter filter){return list(filter,RequestOptions.defaults());}
public CompletableFuture<IndexPage> listAsync(IndexFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge-indexes",null,options,transport.type(IndexPage.class));}
public CompletableFuture<IndexPage> listAsync(IndexFilter filter){return listAsync(filter,RequestOptions.defaults());}
public NativeIndexPage choices(IndexFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge-index-choices",null,options,transport.type(NativeIndexPage.class));}
public NativeIndexPage choices(IndexFilter filter){return choices(filter,RequestOptions.defaults());}
public CompletableFuture<NativeIndexPage> choicesAsync(IndexFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge-index-choices",null,options,transport.type(NativeIndexPage.class));}
public CompletableFuture<NativeIndexPage> choicesAsync(IndexFilter filter){return choicesAsync(filter,RequestOptions.defaults());}
public NativeIndexChoice choice(String choiceId,IndexScope filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge-index-choices/"+Transport.id(choiceId),null,options,transport.type(NativeIndexChoice.class));}
public NativeIndexChoice choice(String choiceId,IndexScope filter){return choice(choiceId,filter,RequestOptions.defaults());}
public CompletableFuture<NativeIndexChoice> choiceAsync(String choiceId,IndexScope filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge-index-choices/"+Transport.id(choiceId),null,options,transport.type(NativeIndexChoice.class));}
public CompletableFuture<NativeIndexChoice> choiceAsync(String choiceId,IndexScope filter){return choiceAsync(choiceId,filter,RequestOptions.defaults());}
public KnowledgeIndexView get(String indexId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge-indexes/"+Transport.id(indexId),null,options,transport.type(KnowledgeIndexView.class));}
public KnowledgeIndexView get(String indexId){return get(indexId,RequestOptions.defaults());}
public CompletableFuture<KnowledgeIndexView> getAsync(String indexId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge-indexes/"+Transport.id(indexId),null,options,transport.type(KnowledgeIndexView.class));}
public CompletableFuture<KnowledgeIndexView> getAsync(String indexId){return getAsync(indexId,RequestOptions.defaults());}
public IndexPlanView plan(IndexPlanInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-indexes/plan",input,options,transport.type(IndexPlanView.class));}
public IndexPlanView plan(IndexPlanInput input){return plan(input,RequestOptions.defaults());}
public CompletableFuture<IndexPlanView> planAsync(IndexPlanInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-indexes/plan",input,options,transport.type(IndexPlanView.class));}
public CompletableFuture<IndexPlanView> planAsync(IndexPlanInput input){return planAsync(input,RequestOptions.defaults());}
public IndexJobView create(IndexCreateInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-indexes",input,options,transport.type(IndexJobView.class));}
public IndexJobView create(IndexCreateInput input,String idempotencyKey){return create(input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<IndexJobView> createAsync(IndexCreateInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-indexes",input,options,transport.type(IndexJobView.class));}
public CompletableFuture<IndexJobView> createAsync(IndexCreateInput input,String idempotencyKey){return createAsync(input,idempotencyKey,RequestOptions.defaults());}
public KnowledgeIndexView activate(String indexId,IndexActivateInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-indexes/"+Transport.id(indexId)+"/activate",input,options,transport.type(KnowledgeIndexView.class));}
public KnowledgeIndexView activate(String indexId,IndexActivateInput input){return activate(indexId,input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeIndexView> activateAsync(String indexId,IndexActivateInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-indexes/"+Transport.id(indexId)+"/activate",input,options,transport.type(KnowledgeIndexView.class));}
public CompletableFuture<KnowledgeIndexView> activateAsync(String indexId,IndexActivateInput input){return activateAsync(indexId,input,RequestOptions.defaults());}
public KnowledgeIndexView cancel(String indexId,IndexRevisionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-indexes/"+Transport.id(indexId)+"/cancel",input,options,transport.type(KnowledgeIndexView.class));}
public KnowledgeIndexView cancel(String indexId,IndexRevisionInput input){return cancel(indexId,input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeIndexView> cancelAsync(String indexId,IndexRevisionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-indexes/"+Transport.id(indexId)+"/cancel",input,options,transport.type(KnowledgeIndexView.class));}
public CompletableFuture<KnowledgeIndexView> cancelAsync(String indexId,IndexRevisionInput input){return cancelAsync(indexId,input,RequestOptions.defaults());}
public IndexJobView resume(String indexId,IndexRevisionInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-indexes/"+Transport.id(indexId)+"/resume",input,options,transport.type(IndexJobView.class));}
public IndexJobView resume(String indexId,IndexRevisionInput input,String idempotencyKey){return resume(indexId,input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<IndexJobView> resumeAsync(String indexId,IndexRevisionInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-indexes/"+Transport.id(indexId)+"/resume",input,options,transport.type(IndexJobView.class));}
public CompletableFuture<IndexJobView> resumeAsync(String indexId,IndexRevisionInput input,String idempotencyKey){return resumeAsync(indexId,input,idempotencyKey,RequestOptions.defaults());}
}

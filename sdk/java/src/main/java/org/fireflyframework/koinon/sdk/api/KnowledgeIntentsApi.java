// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class KnowledgeIntentsApi {
private final Transport transport; private final String prefix;
public KnowledgeIntentsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public KnowledgeIntent preview(KnowledgeIntentInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-intents",input,options,transport.type(KnowledgeIntent.class));}
public KnowledgeIntent preview(KnowledgeIntentInput input){return preview(input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeIntent> previewAsync(KnowledgeIntentInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-intents",input,options,transport.type(KnowledgeIntent.class));}
public CompletableFuture<KnowledgeIntent> previewAsync(KnowledgeIntentInput input){return previewAsync(input,RequestOptions.defaults());}
public KnowledgeIntent get(String intentId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge-intents/"+Transport.id(intentId),null,options,transport.type(KnowledgeIntent.class));}
public KnowledgeIntent get(String intentId){return get(intentId,RequestOptions.defaults());}
public CompletableFuture<KnowledgeIntent> getAsync(String intentId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge-intents/"+Transport.id(intentId),null,options,transport.type(KnowledgeIntent.class));}
public CompletableFuture<KnowledgeIntent> getAsync(String intentId){return getAsync(intentId,RequestOptions.defaults());}
public KnowledgeCommitOutcome confirm(String intentId,KnowledgeConfirmation input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-intents/"+Transport.id(intentId)+"/confirm",input,options,transport.type(KnowledgeCommitOutcome.class));}
public KnowledgeCommitOutcome confirm(String intentId,KnowledgeConfirmation input,String idempotencyKey){return confirm(intentId,input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<KnowledgeCommitOutcome> confirmAsync(String intentId,KnowledgeConfirmation input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-intents/"+Transport.id(intentId)+"/confirm",input,options,transport.type(KnowledgeCommitOutcome.class));}
public CompletableFuture<KnowledgeCommitOutcome> confirmAsync(String intentId,KnowledgeConfirmation input,String idempotencyKey){return confirmAsync(intentId,input,idempotencyKey,RequestOptions.defaults());}
public KnowledgeIntent cancel(String intentId,KnowledgeCancellation input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge-intents/"+Transport.id(intentId)+"/cancel",input,options,transport.type(KnowledgeIntent.class));}
public KnowledgeIntent cancel(String intentId,KnowledgeCancellation input){return cancel(intentId,input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeIntent> cancelAsync(String intentId,KnowledgeCancellation input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge-intents/"+Transport.id(intentId)+"/cancel",input,options,transport.type(KnowledgeIntent.class));}
public CompletableFuture<KnowledgeIntent> cancelAsync(String intentId,KnowledgeCancellation input){return cancelAsync(intentId,input,RequestOptions.defaults());}
}

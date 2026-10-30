// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ExternalReviewsApi {
private final Transport transport; private final String prefix;
public ExternalReviewsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public ExternalReviewView stage(ExternalReviewInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-knowledge-reviews",input,options,transport.type(ExternalReviewView.class));}
public ExternalReviewView stage(ExternalReviewInput input,String idempotencyKey){return stage(input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<ExternalReviewView> stageAsync(ExternalReviewInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-knowledge-reviews",input,options,transport.type(ExternalReviewView.class));}
public CompletableFuture<ExternalReviewView> stageAsync(ExternalReviewInput input,String idempotencyKey){return stageAsync(input,idempotencyKey,RequestOptions.defaults());}
public ExternalReviewView get(String reviewId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/external-knowledge-reviews/"+Transport.id(reviewId),null,options,transport.type(ExternalReviewView.class));}
public ExternalReviewView get(String reviewId){return get(reviewId,RequestOptions.defaults());}
public CompletableFuture<ExternalReviewView> getAsync(String reviewId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/external-knowledge-reviews/"+Transport.id(reviewId),null,options,transport.type(ExternalReviewView.class));}
public CompletableFuture<ExternalReviewView> getAsync(String reviewId){return getAsync(reviewId,RequestOptions.defaults());}
public KnowledgeCommitOutcome approve(String reviewId,ExternalReviewDecision input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-knowledge-reviews/"+Transport.id(reviewId)+"/approve",input,options,transport.type(KnowledgeCommitOutcome.class));}
public KnowledgeCommitOutcome approve(String reviewId,ExternalReviewDecision input,String idempotencyKey){return approve(reviewId,input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<KnowledgeCommitOutcome> approveAsync(String reviewId,ExternalReviewDecision input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-knowledge-reviews/"+Transport.id(reviewId)+"/approve",input,options,transport.type(KnowledgeCommitOutcome.class));}
public CompletableFuture<KnowledgeCommitOutcome> approveAsync(String reviewId,ExternalReviewDecision input,String idempotencyKey){return approveAsync(reviewId,input,idempotencyKey,RequestOptions.defaults());}
public ExternalReviewView cancel(String reviewId,ExternalReviewDecision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-knowledge-reviews/"+Transport.id(reviewId)+"/cancel",input,options,transport.type(ExternalReviewView.class));}
public ExternalReviewView cancel(String reviewId,ExternalReviewDecision input){return cancel(reviewId,input,RequestOptions.defaults());}
public CompletableFuture<ExternalReviewView> cancelAsync(String reviewId,ExternalReviewDecision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-knowledge-reviews/"+Transport.id(reviewId)+"/cancel",input,options,transport.type(ExternalReviewView.class));}
public CompletableFuture<ExternalReviewView> cancelAsync(String reviewId,ExternalReviewDecision input){return cancelAsync(reviewId,input,RequestOptions.defaults());}
}

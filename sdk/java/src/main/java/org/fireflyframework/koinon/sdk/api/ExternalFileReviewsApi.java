// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ExternalFileReviewsApi {
private final Transport transport; private final String prefix;
public ExternalFileReviewsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public ExternalFileCleanupResult cleanup(ExternalFileCleanupInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-file-reviews/cleanup",input,options,transport.type(ExternalFileCleanupResult.class));}
public ExternalFileCleanupResult cleanup(ExternalFileCleanupInput input){return cleanup(input,RequestOptions.defaults());}
public CompletableFuture<ExternalFileCleanupResult> cleanupAsync(ExternalFileCleanupInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-file-reviews/cleanup",input,options,transport.type(ExternalFileCleanupResult.class));}
public CompletableFuture<ExternalFileCleanupResult> cleanupAsync(ExternalFileCleanupInput input){return cleanupAsync(input,RequestOptions.defaults());}
public ExternalFileReviewView stage(ExternalFileReviewInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-file-reviews",input,options,transport.type(ExternalFileReviewView.class));}
public ExternalFileReviewView stage(ExternalFileReviewInput input,String idempotencyKey){return stage(input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<ExternalFileReviewView> stageAsync(ExternalFileReviewInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-file-reviews",input,options,transport.type(ExternalFileReviewView.class));}
public CompletableFuture<ExternalFileReviewView> stageAsync(ExternalFileReviewInput input,String idempotencyKey){return stageAsync(input,idempotencyKey,RequestOptions.defaults());}
public ExternalFileReviewView get(String reviewId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/external-file-reviews/"+Transport.id(reviewId),null,options,transport.type(ExternalFileReviewView.class));}
public ExternalFileReviewView get(String reviewId){return get(reviewId,RequestOptions.defaults());}
public CompletableFuture<ExternalFileReviewView> getAsync(String reviewId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/external-file-reviews/"+Transport.id(reviewId),null,options,transport.type(ExternalFileReviewView.class));}
public CompletableFuture<ExternalFileReviewView> getAsync(String reviewId){return getAsync(reviewId,RequestOptions.defaults());}
public ExternalFileReviewView chunk(String reviewId,ExternalFileChunkInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/chunks",input,options,transport.type(ExternalFileReviewView.class));}
public ExternalFileReviewView chunk(String reviewId,ExternalFileChunkInput input){return chunk(reviewId,input,RequestOptions.defaults());}
public CompletableFuture<ExternalFileReviewView> chunkAsync(String reviewId,ExternalFileChunkInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/chunks",input,options,transport.type(ExternalFileReviewView.class));}
public CompletableFuture<ExternalFileReviewView> chunkAsync(String reviewId,ExternalFileChunkInput input){return chunkAsync(reviewId,input,RequestOptions.defaults());}
public ExternalFileReviewView seal(String reviewId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/seal",null,options,transport.type(ExternalFileReviewView.class));}
public ExternalFileReviewView seal(String reviewId){return seal(reviewId,RequestOptions.defaults());}
public CompletableFuture<ExternalFileReviewView> sealAsync(String reviewId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/seal",null,options,transport.type(ExternalFileReviewView.class));}
public CompletableFuture<ExternalFileReviewView> sealAsync(String reviewId){return sealAsync(reviewId,RequestOptions.defaults());}
public ExternalFileReviewView approve(String reviewId,ExternalReviewDecision input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/approve",input,options,transport.type(ExternalFileReviewView.class));}
public ExternalFileReviewView approve(String reviewId,ExternalReviewDecision input,String idempotencyKey){return approve(reviewId,input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<ExternalFileReviewView> approveAsync(String reviewId,ExternalReviewDecision input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/approve",input,options,transport.type(ExternalFileReviewView.class));}
public CompletableFuture<ExternalFileReviewView> approveAsync(String reviewId,ExternalReviewDecision input,String idempotencyKey){return approveAsync(reviewId,input,idempotencyKey,RequestOptions.defaults());}
public ExternalFileReviewView cancel(String reviewId,ExternalReviewDecision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/cancel",input,options,transport.type(ExternalFileReviewView.class));}
public ExternalFileReviewView cancel(String reviewId,ExternalReviewDecision input){return cancel(reviewId,input,RequestOptions.defaults());}
public CompletableFuture<ExternalFileReviewView> cancelAsync(String reviewId,ExternalReviewDecision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/external-file-reviews/"+Transport.id(reviewId)+"/cancel",input,options,transport.type(ExternalFileReviewView.class));}
public CompletableFuture<ExternalFileReviewView> cancelAsync(String reviewId,ExternalReviewDecision input){return cancelAsync(reviewId,input,RequestOptions.defaults());}
}

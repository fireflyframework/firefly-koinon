// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ChatApi {
private final Transport transport; private final String prefix;
public ChatApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<ChatThread> threads(ThreadFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/chat/threads",null,options,transport.pageType(ChatThread.class));}
public Page<ChatThread> threads(ThreadFilter filter){return threads(filter,RequestOptions.defaults());}
public Page<ChatThread> threads(){return threads(ThreadFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<ChatThread>> threadsAsync(ThreadFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/chat/threads",null,options,transport.pageType(ChatThread.class));}
public CompletableFuture<Page<ChatThread>> threadsAsync(ThreadFilter filter){return threadsAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<ChatThread>> threadsAsync(){return threadsAsync(ThreadFilter.empty(),RequestOptions.defaults());}
public ChatThread createThread(ThreadInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/chat/threads",input,options,transport.type(ChatThread.class));}
public ChatThread createThread(ThreadInput input){return createThread(input,RequestOptions.defaults());}
public CompletableFuture<ChatThread> createThreadAsync(ThreadInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/chat/threads",input,options,transport.type(ChatThread.class));}
public CompletableFuture<ChatThread> createThreadAsync(ThreadInput input){return createThreadAsync(input,RequestOptions.defaults());}
public Page<ChatMessage> messages(String threadId,MessageFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/chat/threads/"+Transport.id(threadId)+"/messages",null,options,transport.pageType(ChatMessage.class));}
public Page<ChatMessage> messages(String threadId,MessageFilter filter){return messages(threadId,filter,RequestOptions.defaults());}
public Page<ChatMessage> messages(String threadId){return messages(threadId,MessageFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<ChatMessage>> messagesAsync(String threadId,MessageFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/chat/threads/"+Transport.id(threadId)+"/messages",null,options,transport.pageType(ChatMessage.class));}
public CompletableFuture<Page<ChatMessage>> messagesAsync(String threadId,MessageFilter filter){return messagesAsync(threadId,filter,RequestOptions.defaults());}
public CompletableFuture<Page<ChatMessage>> messagesAsync(String threadId){return messagesAsync(threadId,MessageFilter.empty(),RequestOptions.defaults());}
public ChatRun submit(String threadId,RunInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/chat/threads/"+Transport.id(threadId)+"/runs",input,options,transport.type(ChatRun.class));}
public ChatRun submit(String threadId,RunInput input){return submit(threadId,input,RequestOptions.defaults());}
public CompletableFuture<ChatRun> submitAsync(String threadId,RunInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/chat/threads/"+Transport.id(threadId)+"/runs",input,options,transport.type(ChatRun.class));}
public CompletableFuture<ChatRun> submitAsync(String threadId,RunInput input){return submitAsync(threadId,input,RequestOptions.defaults());}
public ChatRun cancel(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/cancel",null,options,transport.type(ChatRun.class));}
public ChatRun cancel(String runId){return cancel(runId,RequestOptions.defaults());}
public CompletableFuture<ChatRun> cancelAsync(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/cancel",null,options,transport.type(ChatRun.class));}
public CompletableFuture<ChatRun> cancelAsync(String runId){return cancelAsync(runId,RequestOptions.defaults());}
public ChatRun retry(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/retry",null,options,transport.type(ChatRun.class));}
public ChatRun retry(String runId){return retry(runId,RequestOptions.defaults());}
public CompletableFuture<ChatRun> retryAsync(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/retry",null,options,transport.type(ChatRun.class));}
public CompletableFuture<ChatRun> retryAsync(String runId){return retryAsync(runId,RequestOptions.defaults());}
public EventStream<StreamEvent> events(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.stream(prefix+"/chat/runs/"+Transport.id(runId)+"/events",options,StreamEvent.class);}
public EventStream<StreamEvent> events(String runId){return events(runId,RequestOptions.defaults());}
public EvidenceResult result(String runId,String resultId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/results/"+Transport.id(resultId),null,options,transport.type(EvidenceResult.class));}
public EvidenceResult result(String runId,String resultId){return result(runId,resultId,RequestOptions.defaults());}
public CompletableFuture<EvidenceResult> resultAsync(String runId,String resultId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/results/"+Transport.id(resultId),null,options,transport.type(EvidenceResult.class));}
public CompletableFuture<EvidenceResult> resultAsync(String runId,String resultId){return resultAsync(runId,resultId,RequestOptions.defaults());}
public Page<ToolActivity> activities(String runId,ActivityFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/activity",null,options,transport.pageType(ToolActivity.class));}
public Page<ToolActivity> activities(String runId,ActivityFilter filter){return activities(runId,filter,RequestOptions.defaults());}
public Page<ToolActivity> activities(String runId){return activities(runId,ActivityFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<ToolActivity>> activitiesAsync(String runId,ActivityFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/activity",null,options,transport.pageType(ToolActivity.class));}
public CompletableFuture<Page<ToolActivity>> activitiesAsync(String runId,ActivityFilter filter){return activitiesAsync(runId,filter,RequestOptions.defaults());}
public CompletableFuture<Page<ToolActivity>> activitiesAsync(String runId){return activitiesAsync(runId,ActivityFilter.empty(),RequestOptions.defaults());}
public AnswerAudit audit(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/audit",null,options,transport.type(AnswerAudit.class));}
public AnswerAudit audit(String runId){return audit(runId,RequestOptions.defaults());}
public CompletableFuture<AnswerAudit> auditAsync(String runId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/audit",null,options,transport.type(AnswerAudit.class));}
public CompletableFuture<AnswerAudit> auditAsync(String runId){return auditAsync(runId,RequestOptions.defaults());}
public ChatThread get(String threadId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/chat/threads/"+Transport.id(threadId),null,options,transport.type(ChatThread.class));}
public ChatThread get(String threadId){return get(threadId,RequestOptions.defaults());}
public CompletableFuture<ChatThread> getAsync(String threadId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/chat/threads/"+Transport.id(threadId),null,options,transport.type(ChatThread.class));}
public CompletableFuture<ChatThread> getAsync(String threadId){return getAsync(threadId,RequestOptions.defaults());}
public ChatThread update(String threadId,ThreadPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/chat/threads/"+Transport.id(threadId),input,options,transport.type(ChatThread.class));}
public ChatThread update(String threadId,ThreadPatch input){return update(threadId,input,RequestOptions.defaults());}
public CompletableFuture<ChatThread> updateAsync(String threadId,ThreadPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/chat/threads/"+Transport.id(threadId),input,options,transport.type(ChatThread.class));}
public CompletableFuture<ChatThread> updateAsync(String threadId,ThreadPatch input){return updateAsync(threadId,input,RequestOptions.defaults());}
public TitleSuggestion suggestTitle(String threadId,TitleRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/chat/threads/"+Transport.id(threadId)+"/title-suggestion",input,options,transport.type(TitleSuggestion.class));}
public TitleSuggestion suggestTitle(String threadId,TitleRequest input){return suggestTitle(threadId,input,RequestOptions.defaults());}
public CompletableFuture<TitleSuggestion> suggestTitleAsync(String threadId,TitleRequest input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/chat/threads/"+Transport.id(threadId)+"/title-suggestion",input,options,transport.type(TitleSuggestion.class));}
public CompletableFuture<TitleSuggestion> suggestTitleAsync(String threadId,TitleRequest input){return suggestTitleAsync(threadId,input,RequestOptions.defaults());}
public Void delete(String threadId,ThreadDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("DELETE",prefix+"/chat/threads/"+Transport.id(threadId),null,options,transport.type(Void.class));}
public Void delete(String threadId,ThreadDeleteFilter filter){return delete(threadId,filter,RequestOptions.defaults());}
public CompletableFuture<Void> deleteAsync(String threadId,ThreadDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("DELETE",prefix+"/chat/threads/"+Transport.id(threadId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> deleteAsync(String threadId,ThreadDeleteFilter filter){return deleteAsync(threadId,filter,RequestOptions.defaults());}
}

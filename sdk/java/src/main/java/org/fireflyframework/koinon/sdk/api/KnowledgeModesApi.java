// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class KnowledgeModesApi {
private final Transport transport; private final String prefix;
public KnowledgeModesApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public KnowledgeModeTransitionView create(OrganizationKnowledgeSettingsInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge/settings/transitions",input,options,transport.type(KnowledgeModeTransitionView.class));}
public KnowledgeModeTransitionView create(OrganizationKnowledgeSettingsInput input,String idempotencyKey){return create(input,idempotencyKey,RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeTransitionView> createAsync(OrganizationKnowledgeSettingsInput input,String idempotencyKey,RequestOptions options){Objects.requireNonNull(options);options=options.idempotencyKey(Objects.requireNonNull(idempotencyKey));Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge/settings/transitions",input,options,transport.type(KnowledgeModeTransitionView.class));}
public CompletableFuture<KnowledgeModeTransitionView> createAsync(OrganizationKnowledgeSettingsInput input,String idempotencyKey){return createAsync(input,idempotencyKey,RequestOptions.defaults());}
public KnowledgeModeCurrentView current(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge/settings/transitions/current",null,options,transport.type(KnowledgeModeCurrentView.class));}
public KnowledgeModeCurrentView current(){return current(RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeCurrentView> currentAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge/settings/transitions/current",null,options,transport.type(KnowledgeModeCurrentView.class));}
public CompletableFuture<KnowledgeModeCurrentView> currentAsync(){return currentAsync(RequestOptions.defaults());}
public KnowledgeModeTransitionView get(String transitionId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId),null,options,transport.type(KnowledgeModeTransitionView.class));}
public KnowledgeModeTransitionView get(String transitionId){return get(transitionId,RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeTransitionView> getAsync(String transitionId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId),null,options,transport.type(KnowledgeModeTransitionView.class));}
public CompletableFuture<KnowledgeModeTransitionView> getAsync(String transitionId){return getAsync(transitionId,RequestOptions.defaults());}
public KnowledgeModeTargetPage targets(String transitionId,KnowledgeModeTargetFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/targets",null,options,transport.type(KnowledgeModeTargetPage.class));}
public KnowledgeModeTargetPage targets(String transitionId,KnowledgeModeTargetFilter filter){return targets(transitionId,filter,RequestOptions.defaults());}
public KnowledgeModeTargetPage targets(String transitionId){return targets(transitionId,KnowledgeModeTargetFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeTargetPage> targetsAsync(String transitionId,KnowledgeModeTargetFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/targets",null,options,transport.type(KnowledgeModeTargetPage.class));}
public CompletableFuture<KnowledgeModeTargetPage> targetsAsync(String transitionId,KnowledgeModeTargetFilter filter){return targetsAsync(transitionId,filter,RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeTargetPage> targetsAsync(String transitionId){return targetsAsync(transitionId,KnowledgeModeTargetFilter.empty(),RequestOptions.defaults());}
public KnowledgeModeRecoveryPage recoveries(String transitionId,KnowledgeModeRecoveryFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/recoveries",null,options,transport.type(KnowledgeModeRecoveryPage.class));}
public KnowledgeModeRecoveryPage recoveries(String transitionId,KnowledgeModeRecoveryFilter filter){return recoveries(transitionId,filter,RequestOptions.defaults());}
public KnowledgeModeRecoveryPage recoveries(String transitionId){return recoveries(transitionId,KnowledgeModeRecoveryFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeRecoveryPage> recoveriesAsync(String transitionId,KnowledgeModeRecoveryFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/recoveries",null,options,transport.type(KnowledgeModeRecoveryPage.class));}
public CompletableFuture<KnowledgeModeRecoveryPage> recoveriesAsync(String transitionId,KnowledgeModeRecoveryFilter filter){return recoveriesAsync(transitionId,filter,RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeRecoveryPage> recoveriesAsync(String transitionId){return recoveriesAsync(transitionId,KnowledgeModeRecoveryFilter.empty(),RequestOptions.defaults());}
public KnowledgeModeTransitionView cancel(String transitionId,KnowledgeModeRevisionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/cancel",input,options,transport.type(KnowledgeModeTransitionView.class));}
public KnowledgeModeTransitionView cancel(String transitionId,KnowledgeModeRevisionInput input){return cancel(transitionId,input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeTransitionView> cancelAsync(String transitionId,KnowledgeModeRevisionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/cancel",input,options,transport.type(KnowledgeModeTransitionView.class));}
public CompletableFuture<KnowledgeModeTransitionView> cancelAsync(String transitionId,KnowledgeModeRevisionInput input){return cancelAsync(transitionId,input,RequestOptions.defaults());}
public KnowledgeModeTransitionView retry(String transitionId,KnowledgeModeRevisionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/retry",input,options,transport.type(KnowledgeModeTransitionView.class));}
public KnowledgeModeTransitionView retry(String transitionId,KnowledgeModeRevisionInput input){return retry(transitionId,input,RequestOptions.defaults());}
public CompletableFuture<KnowledgeModeTransitionView> retryAsync(String transitionId,KnowledgeModeRevisionInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/knowledge/settings/transitions/"+Transport.id(transitionId)+"/retry",input,options,transport.type(KnowledgeModeTransitionView.class));}
public CompletableFuture<KnowledgeModeTransitionView> retryAsync(String transitionId,KnowledgeModeRevisionInput input){return retryAsync(transitionId,input,RequestOptions.defaults());}
}

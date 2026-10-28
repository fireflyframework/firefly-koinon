// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class AgentsApi {
private final Transport transport; private final String prefix;
public AgentsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<AgentConfiguration> list(AgentFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/agents",null,options,transport.pageType(AgentConfiguration.class));}
public Page<AgentConfiguration> list(AgentFilter filter){return list(filter,RequestOptions.defaults());}
public Page<AgentConfiguration> list(){return list(AgentFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<AgentConfiguration>> listAsync(AgentFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/agents",null,options,transport.pageType(AgentConfiguration.class));}
public CompletableFuture<Page<AgentConfiguration>> listAsync(AgentFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<AgentConfiguration>> listAsync(){return listAsync(AgentFilter.empty(),RequestOptions.defaults());}
public AgentConfiguration create(AgentInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/agents",input,options,transport.type(AgentConfiguration.class));}
public AgentConfiguration create(AgentInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<AgentConfiguration> createAsync(AgentInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/agents",input,options,transport.type(AgentConfiguration.class));}
public CompletableFuture<AgentConfiguration> createAsync(AgentInput input){return createAsync(input,RequestOptions.defaults());}
public AgentConfiguration update(String agentId,AgentInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/agents/"+Transport.id(agentId),input,options,transport.type(AgentConfiguration.class));}
public AgentConfiguration update(String agentId,AgentInput input){return update(agentId,input,RequestOptions.defaults());}
public CompletableFuture<AgentConfiguration> updateAsync(String agentId,AgentInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/agents/"+Transport.id(agentId),input,options,transport.type(AgentConfiguration.class));}
public CompletableFuture<AgentConfiguration> updateAsync(String agentId,AgentInput input){return updateAsync(agentId,input,RequestOptions.defaults());}
public AgentConfiguration validate(String agentId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/agents/"+Transport.id(agentId)+"/validate",null,options,transport.type(AgentConfiguration.class));}
public AgentConfiguration validate(String agentId){return validate(agentId,RequestOptions.defaults());}
public CompletableFuture<AgentConfiguration> validateAsync(String agentId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/agents/"+Transport.id(agentId)+"/validate",null,options,transport.type(AgentConfiguration.class));}
public CompletableFuture<AgentConfiguration> validateAsync(String agentId){return validateAsync(agentId,RequestOptions.defaults());}
}

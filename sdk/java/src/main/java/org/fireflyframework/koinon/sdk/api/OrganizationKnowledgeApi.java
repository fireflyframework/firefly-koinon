// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class OrganizationKnowledgeApi {
private final Transport transport; private final String prefix;
public OrganizationKnowledgeApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public OrganizationKnowledgeSettings get(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/knowledge/settings",null,options,transport.type(OrganizationKnowledgeSettings.class));}
public OrganizationKnowledgeSettings get(){return get(RequestOptions.defaults());}
public CompletableFuture<OrganizationKnowledgeSettings> getAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/knowledge/settings",null,options,transport.type(OrganizationKnowledgeSettings.class));}
public CompletableFuture<OrganizationKnowledgeSettings> getAsync(){return getAsync(RequestOptions.defaults());}
public OrganizationKnowledgeSettings update(OrganizationKnowledgeSettingsInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PUT",prefix+"/knowledge/settings",input,options,transport.type(OrganizationKnowledgeSettings.class));}
public OrganizationKnowledgeSettings update(OrganizationKnowledgeSettingsInput input){return update(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationKnowledgeSettings> updateAsync(OrganizationKnowledgeSettingsInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PUT",prefix+"/knowledge/settings",input,options,transport.type(OrganizationKnowledgeSettings.class));}
public CompletableFuture<OrganizationKnowledgeSettings> updateAsync(OrganizationKnowledgeSettingsInput input){return updateAsync(input,RequestOptions.defaults());}
}

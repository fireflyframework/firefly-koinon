// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class OrganizationChatApi {
private final Transport transport; private final String prefix;
public OrganizationChatApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public OrganizationChatSettings get(OrganizationChatFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/chat/settings",null,options,transport.type(OrganizationChatSettings.class));}
public OrganizationChatSettings get(OrganizationChatFilter filter){return get(filter,RequestOptions.defaults());}
public OrganizationChatSettings get(){return get(OrganizationChatFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationChatSettings> getAsync(OrganizationChatFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/chat/settings",null,options,transport.type(OrganizationChatSettings.class));}
public CompletableFuture<OrganizationChatSettings> getAsync(OrganizationChatFilter filter){return getAsync(filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationChatSettings> getAsync(){return getAsync(OrganizationChatFilter.empty(),RequestOptions.defaults());}
public OrganizationChatSettings update(OrganizationChatSettingsInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PUT",prefix+"/chat/settings",input,options,transport.type(OrganizationChatSettings.class));}
public OrganizationChatSettings update(OrganizationChatSettingsInput input){return update(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationChatSettings> updateAsync(OrganizationChatSettingsInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PUT",prefix+"/chat/settings",input,options,transport.type(OrganizationChatSettings.class));}
public CompletableFuture<OrganizationChatSettings> updateAsync(OrganizationChatSettingsInput input){return updateAsync(input,RequestOptions.defaults());}
}

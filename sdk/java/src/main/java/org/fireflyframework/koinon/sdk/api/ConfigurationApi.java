// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ConfigurationApi {
private final Transport transport; private final String prefix;
public ConfigurationApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Configuration get(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/configuration",null,options,transport.type(Configuration.class));}
public Configuration get(){return get(RequestOptions.defaults());}
public CompletableFuture<Configuration> getAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/configuration",null,options,transport.type(Configuration.class));}
public CompletableFuture<Configuration> getAsync(){return getAsync(RequestOptions.defaults());}
}

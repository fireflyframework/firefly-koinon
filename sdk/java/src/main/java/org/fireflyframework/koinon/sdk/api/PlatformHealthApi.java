// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class PlatformHealthApi {
private final Transport transport; private final String prefix;
public PlatformHealthApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public PlatformHealth health(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/platform/health",null,options,transport.type(PlatformHealth.class));}
public PlatformHealth health(){return health(RequestOptions.defaults());}
public CompletableFuture<PlatformHealth> healthAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/platform/health",null,options,transport.type(PlatformHealth.class));}
public CompletableFuture<PlatformHealth> healthAsync(){return healthAsync(RequestOptions.defaults());}
public SystemInformation systemInformation(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/platform/system-information",null,options,transport.type(SystemInformation.class));}
public SystemInformation systemInformation(){return systemInformation(RequestOptions.defaults());}
public CompletableFuture<SystemInformation> systemInformationAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/platform/system-information",null,options,transport.type(SystemInformation.class));}
public CompletableFuture<SystemInformation> systemInformationAsync(){return systemInformationAsync(RequestOptions.defaults());}
}

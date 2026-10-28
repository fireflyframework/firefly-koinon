// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class PlatformApi {
private final Transport transport; private final String prefix;
public PlatformApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public ContextResponse context(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/context",null,options,transport.type(ContextResponse.class));}
public ContextResponse context(){return context(RequestOptions.defaults());}
public CompletableFuture<ContextResponse> contextAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/context",null,options,transport.type(ContextResponse.class));}
public CompletableFuture<ContextResponse> contextAsync(){return contextAsync(RequestOptions.defaults());}
public Capabilities capabilities(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/capabilities",null,options,transport.type(Capabilities.class));}
public Capabilities capabilities(){return capabilities(RequestOptions.defaults());}
public CompletableFuture<Capabilities> capabilitiesAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/capabilities",null,options,transport.type(Capabilities.class));}
public CompletableFuture<Capabilities> capabilitiesAsync(){return capabilitiesAsync(RequestOptions.defaults());}
}

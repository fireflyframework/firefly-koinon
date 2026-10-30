// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class McpApi {
private final Transport transport; private final String prefix;
public McpApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public McpConnectionDescriptor connection(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/mcp/connection",null,options,transport.type(McpConnectionDescriptor.class));}
public McpConnectionDescriptor connection(){return connection(RequestOptions.defaults());}
public CompletableFuture<McpConnectionDescriptor> connectionAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/mcp/connection",null,options,transport.type(McpConnectionDescriptor.class));}
public CompletableFuture<McpConnectionDescriptor> connectionAsync(){return connectionAsync(RequestOptions.defaults());}
}

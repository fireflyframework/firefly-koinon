// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class BrandingDefaultsApi {
private final Transport transport; private final String prefix;
public BrandingDefaultsApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public BrandingValues defaults(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/branding/defaults",null,options,transport.type(BrandingValues.class));}
public BrandingValues defaults(){return defaults(RequestOptions.defaults());}
public CompletableFuture<BrandingValues> defaultsAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/branding/defaults",null,options,transport.type(BrandingValues.class));}
public CompletableFuture<BrandingValues> defaultsAsync(){return defaultsAsync(RequestOptions.defaults());}
}

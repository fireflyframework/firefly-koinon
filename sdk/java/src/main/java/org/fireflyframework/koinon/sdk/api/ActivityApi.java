// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ActivityApi {
private final Transport transport; private final String prefix;
public ActivityApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public ActivitySummary personal(ActivityWindow input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/activity/personal",input,options,transport.type(ActivitySummary.class));}
public ActivitySummary personal(ActivityWindow input){return personal(input,RequestOptions.defaults());}
public CompletableFuture<ActivitySummary> personalAsync(ActivityWindow input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/activity/personal",input,options,transport.type(ActivitySummary.class));}
public CompletableFuture<ActivitySummary> personalAsync(ActivityWindow input){return personalAsync(input,RequestOptions.defaults());}
public ActivitySummary administrative(ActivityWindow input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/activity/administration",input,options,transport.type(ActivitySummary.class));}
public ActivitySummary administrative(ActivityWindow input){return administrative(input,RequestOptions.defaults());}
public CompletableFuture<ActivitySummary> administrativeAsync(ActivityWindow input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/activity/administration",input,options,transport.type(ActivitySummary.class));}
public CompletableFuture<ActivitySummary> administrativeAsync(ActivityWindow input){return administrativeAsync(input,RequestOptions.defaults());}
}

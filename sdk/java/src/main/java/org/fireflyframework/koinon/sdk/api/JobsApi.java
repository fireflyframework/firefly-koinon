// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class JobsApi {
private final Transport transport; private final String prefix;
public JobsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<Job> list(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/jobs",null,options,transport.pageType(Job.class));}
public Page<Job> list(){return list(RequestOptions.defaults());}
public CompletableFuture<Page<Job>> listAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/jobs",null,options,transport.pageType(Job.class));}
public CompletableFuture<Page<Job>> listAsync(){return listAsync(RequestOptions.defaults());}
public Job get(String jobId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/jobs/"+Transport.id(jobId),null,options,transport.type(Job.class));}
public Job get(String jobId){return get(jobId,RequestOptions.defaults());}
public CompletableFuture<Job> getAsync(String jobId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/jobs/"+Transport.id(jobId),null,options,transport.type(Job.class));}
public CompletableFuture<Job> getAsync(String jobId){return getAsync(jobId,RequestOptions.defaults());}
public Job cancel(String jobId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/jobs/"+Transport.id(jobId)+"/cancel",null,options,transport.type(Job.class));}
public Job cancel(String jobId){return cancel(jobId,RequestOptions.defaults());}
public CompletableFuture<Job> cancelAsync(String jobId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/jobs/"+Transport.id(jobId)+"/cancel",null,options,transport.type(Job.class));}
public CompletableFuture<Job> cancelAsync(String jobId){return cancelAsync(jobId,RequestOptions.defaults());}
}

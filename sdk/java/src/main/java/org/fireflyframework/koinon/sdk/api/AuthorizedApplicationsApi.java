// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class AuthorizedApplicationsApi {
private final Transport transport; private final String prefix;
public AuthorizedApplicationsApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public Page<AuthorizedApplication> list(AuthorizedApplicationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/authorized-applications",null,options,transport.pageType(AuthorizedApplication.class));}
public Page<AuthorizedApplication> list(AuthorizedApplicationFilter filter){return list(filter,RequestOptions.defaults());}
public Page<AuthorizedApplication> list(){return list(AuthorizedApplicationFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<AuthorizedApplication>> listAsync(AuthorizedApplicationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/authorized-applications",null,options,transport.pageType(AuthorizedApplication.class));}
public CompletableFuture<Page<AuthorizedApplication>> listAsync(AuthorizedApplicationFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<AuthorizedApplication>> listAsync(){return listAsync(AuthorizedApplicationFilter.empty(),RequestOptions.defaults());}
public AuthorizedApplication get(String applicationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/authorized-applications/"+Transport.id(applicationId),null,options,transport.type(AuthorizedApplication.class));}
public AuthorizedApplication get(String applicationId){return get(applicationId,RequestOptions.defaults());}
public CompletableFuture<AuthorizedApplication> getAsync(String applicationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/authorized-applications/"+Transport.id(applicationId),null,options,transport.type(AuthorizedApplication.class));}
public CompletableFuture<AuthorizedApplication> getAsync(String applicationId){return getAsync(applicationId,RequestOptions.defaults());}
public Void revoke(String applicationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/authorized-applications/"+Transport.id(applicationId),null,options,transport.type(Void.class));}
public Void revoke(String applicationId){return revoke(applicationId,RequestOptions.defaults());}
public CompletableFuture<Void> revokeAsync(String applicationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/authorized-applications/"+Transport.id(applicationId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> revokeAsync(String applicationId){return revokeAsync(applicationId,RequestOptions.defaults());}
}

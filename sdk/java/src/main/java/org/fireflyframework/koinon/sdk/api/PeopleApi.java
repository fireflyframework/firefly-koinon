// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class PeopleApi {
private final Transport transport; private final String prefix;
public PeopleApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<Person> list(PeopleFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/people",null,options,transport.pageType(Person.class));}
public Page<Person> list(PeopleFilter filter){return list(filter,RequestOptions.defaults());}
public Page<Person> list(){return list(PeopleFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<Person>> listAsync(PeopleFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/people",null,options,transport.pageType(Person.class));}
public CompletableFuture<Page<Person>> listAsync(PeopleFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<Person>> listAsync(){return listAsync(PeopleFilter.empty(),RequestOptions.defaults());}
public BinaryResponse avatar(String profileId,WorkspaceFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.binary("GET",prefix+"/people/"+Transport.id(profileId)+"/avatar",options);}
public BinaryResponse avatar(String profileId,WorkspaceFilter filter){return avatar(profileId,filter,RequestOptions.defaults());}
public BinaryResponse avatar(String profileId){return avatar(profileId,WorkspaceFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> avatarAsync(String profileId,WorkspaceFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.binaryAsync("GET",prefix+"/people/"+Transport.id(profileId)+"/avatar",options);}
public CompletableFuture<BinaryResponse> avatarAsync(String profileId,WorkspaceFilter filter){return avatarAsync(profileId,filter,RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> avatarAsync(String profileId){return avatarAsync(profileId,WorkspaceFilter.empty(),RequestOptions.defaults());}
public FileDownload downloadAvatar(String profileId,WorkspaceFilter filter,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.download("GET",prefix+"/people/"+Transport.id(profileId)+"/avatar",target,maxBytes,options);}
public CompletableFuture<FileDownload> downloadAvatarAsync(String profileId,WorkspaceFilter filter,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.downloadAsync("GET",prefix+"/people/"+Transport.id(profileId)+"/avatar",target,maxBytes,options);}
}

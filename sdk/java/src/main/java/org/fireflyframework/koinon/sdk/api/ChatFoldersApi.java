// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ChatFoldersApi {
private final Transport transport; private final String prefix;
public ChatFoldersApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<ChatFolder> list(FolderFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/chat/folders",null,options,transport.pageType(ChatFolder.class));}
public Page<ChatFolder> list(FolderFilter filter){return list(filter,RequestOptions.defaults());}
public Page<ChatFolder> list(){return list(FolderFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<ChatFolder>> listAsync(FolderFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/chat/folders",null,options,transport.pageType(ChatFolder.class));}
public CompletableFuture<Page<ChatFolder>> listAsync(FolderFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<ChatFolder>> listAsync(){return listAsync(FolderFilter.empty(),RequestOptions.defaults());}
public ChatFolder create(FolderCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/chat/folders",input,options,transport.type(ChatFolder.class));}
public ChatFolder create(FolderCreate input){return create(input,RequestOptions.defaults());}
public CompletableFuture<ChatFolder> createAsync(FolderCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/chat/folders",input,options,transport.type(ChatFolder.class));}
public CompletableFuture<ChatFolder> createAsync(FolderCreate input){return createAsync(input,RequestOptions.defaults());}
public ChatFolder get(String folderId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/chat/folders/"+Transport.id(folderId),null,options,transport.type(ChatFolder.class));}
public ChatFolder get(String folderId){return get(folderId,RequestOptions.defaults());}
public CompletableFuture<ChatFolder> getAsync(String folderId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/chat/folders/"+Transport.id(folderId),null,options,transport.type(ChatFolder.class));}
public CompletableFuture<ChatFolder> getAsync(String folderId){return getAsync(folderId,RequestOptions.defaults());}
public ChatFolder update(String folderId,FolderPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/chat/folders/"+Transport.id(folderId),input,options,transport.type(ChatFolder.class));}
public ChatFolder update(String folderId,FolderPatch input){return update(folderId,input,RequestOptions.defaults());}
public CompletableFuture<ChatFolder> updateAsync(String folderId,FolderPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/chat/folders/"+Transport.id(folderId),input,options,transport.type(ChatFolder.class));}
public CompletableFuture<ChatFolder> updateAsync(String folderId,FolderPatch input){return updateAsync(folderId,input,RequestOptions.defaults());}
public Void delete(String folderId,FolderDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("DELETE",prefix+"/chat/folders/"+Transport.id(folderId),null,options,transport.type(Void.class));}
public Void delete(String folderId,FolderDeleteFilter filter){return delete(folderId,filter,RequestOptions.defaults());}
public CompletableFuture<Void> deleteAsync(String folderId,FolderDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("DELETE",prefix+"/chat/folders/"+Transport.id(folderId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> deleteAsync(String folderId,FolderDeleteFilter filter){return deleteAsync(folderId,filter,RequestOptions.defaults());}
}

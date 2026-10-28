// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ProfileApi {
private final Transport transport; private final String prefix;
public ProfileApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public UserProfile get(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/profile",null,options,transport.type(UserProfile.class));}
public UserProfile get(){return get(RequestOptions.defaults());}
public CompletableFuture<UserProfile> getAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/profile",null,options,transport.type(UserProfile.class));}
public CompletableFuture<UserProfile> getAsync(){return getAsync(RequestOptions.defaults());}
public UserProfile update(ProfileUpdate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/profile",input,options,transport.type(UserProfile.class));}
public UserProfile update(ProfileUpdate input){return update(input,RequestOptions.defaults());}
public CompletableFuture<UserProfile> updateAsync(ProfileUpdate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/profile",input,options,transport.type(UserProfile.class));}
public CompletableFuture<UserProfile> updateAsync(ProfileUpdate input){return updateAsync(input,RequestOptions.defaults());}
public BinaryResponse avatar(RequestOptions options){Objects.requireNonNull(options);return transport.binary("GET",prefix+"/profile/avatar",options);}
public BinaryResponse avatar(){return avatar(RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> avatarAsync(RequestOptions options){Objects.requireNonNull(options);return transport.binaryAsync("GET",prefix+"/profile/avatar",options);}
public CompletableFuture<BinaryResponse> avatarAsync(){return avatarAsync(RequestOptions.defaults());}
public FileDownload downloadAvatar(Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);return transport.download("GET",prefix+"/profile/avatar",target,maxBytes,options);}
public CompletableFuture<FileDownload> downloadAvatarAsync(Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);return transport.downloadAsync("GET",prefix+"/profile/avatar",target,maxBytes,options);}
public UserProfile uploadAvatar(AvatarUpload input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.bytes("POST",prefix+"/profile/avatar",input.content(),input.mediaType().value(),options,transport.type(UserProfile.class));}
public UserProfile uploadAvatar(AvatarUpload input){return uploadAvatar(input,RequestOptions.defaults());}
public CompletableFuture<UserProfile> uploadAvatarAsync(AvatarUpload input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.bytesAsync("POST",prefix+"/profile/avatar",input.content(),input.mediaType().value(),options,transport.type(UserProfile.class));}
public CompletableFuture<UserProfile> uploadAvatarAsync(AvatarUpload input){return uploadAvatarAsync(input,RequestOptions.defaults());}
public UserProfile deleteAvatar(RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/profile/avatar",null,options,transport.type(UserProfile.class));}
public UserProfile deleteAvatar(){return deleteAvatar(RequestOptions.defaults());}
public CompletableFuture<UserProfile> deleteAvatarAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/profile/avatar",null,options,transport.type(UserProfile.class));}
public CompletableFuture<UserProfile> deleteAvatarAsync(){return deleteAvatarAsync(RequestOptions.defaults());}
}

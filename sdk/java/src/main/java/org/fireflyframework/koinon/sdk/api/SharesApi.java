// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class SharesApi {
private final Transport transport; private final String prefix;
public SharesApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public ShareReview review(ShareReviewInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/shares/reviews",input,options,transport.type(ShareReview.class));}
public ShareReview review(ShareReviewInput input){return review(input,RequestOptions.defaults());}
public CompletableFuture<ShareReview> reviewAsync(ShareReviewInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/shares/reviews",input,options,transport.type(ShareReview.class));}
public CompletableFuture<ShareReview> reviewAsync(ShareReviewInput input){return reviewAsync(input,RequestOptions.defaults());}
public Share create(ShareCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/shares",input,options,transport.type(Share.class));}
public Share create(ShareCreate input){return create(input,RequestOptions.defaults());}
public CompletableFuture<Share> createAsync(ShareCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/shares",input,options,transport.type(Share.class));}
public CompletableFuture<Share> createAsync(ShareCreate input){return createAsync(input,RequestOptions.defaults());}
public SharePage list(ShareFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/shares",null,options,transport.type(SharePage.class));}
public SharePage list(ShareFilter filter){return list(filter,RequestOptions.defaults());}
public SharePage list(){return list(ShareFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<SharePage> listAsync(ShareFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/shares",null,options,transport.type(SharePage.class));}
public CompletableFuture<SharePage> listAsync(ShareFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<SharePage> listAsync(){return listAsync(ShareFilter.empty(),RequestOptions.defaults());}
public SharedConversation get(String shareId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/shares/"+Transport.id(shareId),null,options,transport.type(SharedConversation.class));}
public SharedConversation get(String shareId){return get(shareId,RequestOptions.defaults());}
public CompletableFuture<SharedConversation> getAsync(String shareId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/shares/"+Transport.id(shareId),null,options,transport.type(SharedConversation.class));}
public CompletableFuture<SharedConversation> getAsync(String shareId){return getAsync(shareId,RequestOptions.defaults());}
public Void revoke(String shareId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/shares/"+Transport.id(shareId),null,options,transport.type(Void.class));}
public Void revoke(String shareId){return revoke(shareId,RequestOptions.defaults());}
public CompletableFuture<Void> revokeAsync(String shareId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/shares/"+Transport.id(shareId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> revokeAsync(String shareId){return revokeAsync(shareId,RequestOptions.defaults());}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class MembersApi {
private final Transport transport; private final String prefix;
public MembersApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<Membership> list(MembershipFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/members",null,options,transport.pageType(Membership.class));}
public Page<Membership> list(MembershipFilter filter){return list(filter,RequestOptions.defaults());}
public Page<Membership> list(){return list(MembershipFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<Membership>> listAsync(MembershipFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/members",null,options,transport.pageType(Membership.class));}
public CompletableFuture<Page<Membership>> listAsync(MembershipFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<Membership>> listAsync(){return listAsync(MembershipFilter.empty(),RequestOptions.defaults());}
public Membership add(MemberInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/members",input,options,transport.type(Membership.class));}
public Membership add(MemberInput input){return add(input,RequestOptions.defaults());}
public CompletableFuture<Membership> addAsync(MemberInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/members",input,options,transport.type(Membership.class));}
public CompletableFuture<Membership> addAsync(MemberInput input){return addAsync(input,RequestOptions.defaults());}
public Membership update(String memberId,MemberUpdate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/members/"+Transport.id(memberId),input,options,transport.type(Membership.class));}
public Membership update(String memberId,MemberUpdate input){return update(memberId,input,RequestOptions.defaults());}
public CompletableFuture<Membership> updateAsync(String memberId,MemberUpdate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/members/"+Transport.id(memberId),input,options,transport.type(Membership.class));}
public CompletableFuture<Membership> updateAsync(String memberId,MemberUpdate input){return updateAsync(memberId,input,RequestOptions.defaults());}
public Void remove(String memberId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/members/"+Transport.id(memberId),null,options,transport.type(Void.class));}
public Void remove(String memberId){return remove(memberId,RequestOptions.defaults());}
public CompletableFuture<Void> removeAsync(String memberId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/members/"+Transport.id(memberId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> removeAsync(String memberId){return removeAsync(memberId,RequestOptions.defaults());}
}

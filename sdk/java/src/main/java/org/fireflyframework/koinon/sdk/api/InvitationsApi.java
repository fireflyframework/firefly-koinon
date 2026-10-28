// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class InvitationsApi {
private final Transport transport; private final String prefix;
public InvitationsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public Page<Invitation> list(InvitationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/invitations",null,options,transport.pageType(Invitation.class));}
public Page<Invitation> list(InvitationFilter filter){return list(filter,RequestOptions.defaults());}
public Page<Invitation> list(){return list(InvitationFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<Page<Invitation>> listAsync(InvitationFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/invitations",null,options,transport.pageType(Invitation.class));}
public CompletableFuture<Page<Invitation>> listAsync(InvitationFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<Page<Invitation>> listAsync(){return listAsync(InvitationFilter.empty(),RequestOptions.defaults());}
public InvitationCreated create(InvitationInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/invitations",input,options,transport.type(InvitationCreated.class));}
public InvitationCreated create(InvitationInput input){return create(input,RequestOptions.defaults());}
public CompletableFuture<InvitationCreated> createAsync(InvitationInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/invitations",input,options,transport.type(InvitationCreated.class));}
public CompletableFuture<InvitationCreated> createAsync(InvitationInput input){return createAsync(input,RequestOptions.defaults());}
public Void revoke(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("DELETE",prefix+"/invitations/"+Transport.id(invitationId),null,options,transport.type(Void.class));}
public Void revoke(String invitationId){return revoke(invitationId,RequestOptions.defaults());}
public CompletableFuture<Void> revokeAsync(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("DELETE",prefix+"/invitations/"+Transport.id(invitationId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> revokeAsync(String invitationId){return revokeAsync(invitationId,RequestOptions.defaults());}
}

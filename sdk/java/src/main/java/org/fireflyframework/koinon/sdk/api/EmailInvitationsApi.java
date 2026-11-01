// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class EmailInvitationsApi {
private final Transport transport; private final String prefix;
public EmailInvitationsApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public InvitationReview review(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/invitations/email/"+Transport.id(invitationId),null,options,transport.type(InvitationReview.class));}
public InvitationReview review(String invitationId){return review(invitationId,RequestOptions.defaults());}
public CompletableFuture<InvitationReview> reviewAsync(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/invitations/email/"+Transport.id(invitationId),null,options,transport.type(InvitationReview.class));}
public CompletableFuture<InvitationReview> reviewAsync(String invitationId){return reviewAsync(invitationId,RequestOptions.defaults());}
public Membership accept(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/invitations/email/"+Transport.id(invitationId)+"/accept",null,options,transport.type(Membership.class));}
public Membership accept(String invitationId){return accept(invitationId,RequestOptions.defaults());}
public CompletableFuture<Membership> acceptAsync(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/invitations/email/"+Transport.id(invitationId)+"/accept",null,options,transport.type(Membership.class));}
public CompletableFuture<Membership> acceptAsync(String invitationId){return acceptAsync(invitationId,RequestOptions.defaults());}
public InvitationReview decline(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.json("POST",prefix+"/invitations/email/"+Transport.id(invitationId)+"/decline",null,options,transport.type(InvitationReview.class));}
public InvitationReview decline(String invitationId){return decline(invitationId,RequestOptions.defaults());}
public CompletableFuture<InvitationReview> declineAsync(String invitationId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("POST",prefix+"/invitations/email/"+Transport.id(invitationId)+"/decline",null,options,transport.type(InvitationReview.class));}
public CompletableFuture<InvitationReview> declineAsync(String invitationId){return declineAsync(invitationId,RequestOptions.defaults());}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class InvitationAccessApi {
private final Transport transport; private final String prefix;
public InvitationAccessApi(Transport transport){this.transport=Objects.requireNonNull(transport);this.prefix="";}
public InvitationPreview inspect(InvitationToken input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/invitations/inspect",input,options,transport.type(InvitationPreview.class));}
public InvitationPreview inspect(InvitationToken input){return inspect(input,RequestOptions.defaults());}
public CompletableFuture<InvitationPreview> inspectAsync(InvitationToken input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/invitations/inspect",input,options,transport.type(InvitationPreview.class));}
public CompletableFuture<InvitationPreview> inspectAsync(InvitationToken input){return inspectAsync(input,RequestOptions.defaults());}
public Membership redeem(InvitationToken input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/invitations/redeem",input,options,transport.type(Membership.class));}
public Membership redeem(InvitationToken input){return redeem(input,RequestOptions.defaults());}
public CompletableFuture<Membership> redeemAsync(InvitationToken input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/invitations/redeem",input,options,transport.type(Membership.class));}
public CompletableFuture<Membership> redeemAsync(InvitationToken input){return redeemAsync(input,RequestOptions.defaults());}
}

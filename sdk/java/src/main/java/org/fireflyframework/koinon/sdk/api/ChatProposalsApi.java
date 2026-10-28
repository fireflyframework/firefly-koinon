// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class ChatProposalsApi {
private final Transport transport; private final String prefix;
public ChatProposalsApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public CatalogProposal get(String runId,String proposalId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/proposals/"+Transport.id(proposalId),null,options,transport.type(CatalogProposal.class));}
public CatalogProposal get(String runId,String proposalId){return get(runId,proposalId,RequestOptions.defaults());}
public CompletableFuture<CatalogProposal> getAsync(String runId,String proposalId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/chat/runs/"+Transport.id(runId)+"/proposals/"+Transport.id(proposalId),null,options,transport.type(CatalogProposal.class));}
public CompletableFuture<CatalogProposal> getAsync(String runId,String proposalId){return getAsync(runId,proposalId,RequestOptions.defaults());}
public CatalogProposal confirm(String runId,String proposalId,ProposalConfirmation input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/proposals/"+Transport.id(proposalId)+"/confirm",input,options,transport.type(CatalogProposal.class));}
public CatalogProposal confirm(String runId,String proposalId,ProposalConfirmation input){return confirm(runId,proposalId,input,RequestOptions.defaults());}
public CompletableFuture<CatalogProposal> confirmAsync(String runId,String proposalId,ProposalConfirmation input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/proposals/"+Transport.id(proposalId)+"/confirm",input,options,transport.type(CatalogProposal.class));}
public CompletableFuture<CatalogProposal> confirmAsync(String runId,String proposalId,ProposalConfirmation input){return confirmAsync(runId,proposalId,input,RequestOptions.defaults());}
public CatalogProposal cancel(String runId,String proposalId,ProposalRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/proposals/"+Transport.id(proposalId)+"/cancel",input,options,transport.type(CatalogProposal.class));}
public CatalogProposal cancel(String runId,String proposalId,ProposalRevision input){return cancel(runId,proposalId,input,RequestOptions.defaults());}
public CompletableFuture<CatalogProposal> cancelAsync(String runId,String proposalId,ProposalRevision input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/chat/runs/"+Transport.id(runId)+"/proposals/"+Transport.id(proposalId)+"/cancel",input,options,transport.type(CatalogProposal.class));}
public CompletableFuture<CatalogProposal> cancelAsync(String runId,String proposalId,ProposalRevision input){return cancelAsync(runId,proposalId,input,RequestOptions.defaults());}
}

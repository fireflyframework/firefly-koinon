// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record RecipientFilter(String q,String providerId,String workspaceId,String after,Integer limit) {
public static RecipientFilter empty(){return new RecipientFilter(null,null,null,null,null);}
public RecipientFilter withQ(String value){return new RecipientFilter(value,providerId,workspaceId,after,limit);}
public RecipientFilter withProviderId(String value){return new RecipientFilter(q,value,workspaceId,after,limit);}
public RecipientFilter withWorkspaceId(String value){return new RecipientFilter(q,providerId,value,after,limit);}
public RecipientFilter withAfter(String value){return new RecipientFilter(q,providerId,workspaceId,value,limit);}
public RecipientFilter withLimit(Integer value){return new RecipientFilter(q,providerId,workspaceId,after,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(providerId!=null)options=options.query("provider_id",String.valueOf(providerId));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(after!=null)options=options.query("after",String.valueOf(after));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
return options;}
}

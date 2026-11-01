// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record RecipientProviderFilter(String workspaceId,Integer page,Integer pageSize) {
public static RecipientProviderFilter empty(){return new RecipientProviderFilter(null,null,null);}
public RecipientProviderFilter withWorkspaceId(String value){return new RecipientProviderFilter(value,page,pageSize);}
public RecipientProviderFilter withPage(Integer value){return new RecipientProviderFilter(workspaceId,value,pageSize);}
public RecipientProviderFilter withPageSize(Integer value){return new RecipientProviderFilter(workspaceId,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

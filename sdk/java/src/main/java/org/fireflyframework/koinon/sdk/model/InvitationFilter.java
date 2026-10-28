// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record InvitationFilter(String workspaceId,InvitationStatus status,Integer page,Integer pageSize) {
public static InvitationFilter empty(){return new InvitationFilter(null,null,null,null);}
public InvitationFilter withWorkspaceId(String value){return new InvitationFilter(value,status,page,pageSize);}
public InvitationFilter withStatus(InvitationStatus value){return new InvitationFilter(workspaceId,value,page,pageSize);}
public InvitationFilter withPage(Integer value){return new InvitationFilter(workspaceId,status,value,pageSize);}
public InvitationFilter withPageSize(Integer value){return new InvitationFilter(workspaceId,status,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(status!=null)options=options.query("status",status.value());
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

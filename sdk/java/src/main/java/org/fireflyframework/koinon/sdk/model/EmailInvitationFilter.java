// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record EmailInvitationFilter(String workspaceId,String status,Integer page,Integer pageSize) {
public static EmailInvitationFilter empty(){return new EmailInvitationFilter(null,null,null,null);}
public EmailInvitationFilter withWorkspaceId(String value){return new EmailInvitationFilter(value,status,page,pageSize);}
public EmailInvitationFilter withStatus(String value){return new EmailInvitationFilter(workspaceId,value,page,pageSize);}
public EmailInvitationFilter withPage(Integer value){return new EmailInvitationFilter(workspaceId,status,value,pageSize);}
public EmailInvitationFilter withPageSize(Integer value){return new EmailInvitationFilter(workspaceId,status,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(status!=null)options=options.query("status",String.valueOf(status));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

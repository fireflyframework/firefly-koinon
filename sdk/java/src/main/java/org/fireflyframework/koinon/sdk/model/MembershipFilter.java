// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record MembershipFilter(String workspaceId,String q,MembershipRole role,MembershipScope scope,Integer page,Integer pageSize) {
public static MembershipFilter empty(){return new MembershipFilter(null,null,null,null,null,null);}
public MembershipFilter withWorkspaceId(String value){return new MembershipFilter(value,q,role,scope,page,pageSize);}
public MembershipFilter withQ(String value){return new MembershipFilter(workspaceId,value,role,scope,page,pageSize);}
public MembershipFilter withRole(MembershipRole value){return new MembershipFilter(workspaceId,q,value,scope,page,pageSize);}
public MembershipFilter withScope(MembershipScope value){return new MembershipFilter(workspaceId,q,role,value,page,pageSize);}
public MembershipFilter withPage(Integer value){return new MembershipFilter(workspaceId,q,role,scope,value,pageSize);}
public MembershipFilter withPageSize(Integer value){return new MembershipFilter(workspaceId,q,role,scope,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(q!=null)options=options.query("q",String.valueOf(q));
if(role!=null)options=options.query("role",role.value());
if(scope!=null)options=options.query("scope",scope.value());
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

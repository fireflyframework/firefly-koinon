// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record PeopleFilter(String workspaceId,String q,Integer limit,String after) {
public static PeopleFilter empty(){return new PeopleFilter(null,null,null,null);}
public PeopleFilter withWorkspaceId(String value){return new PeopleFilter(value,q,limit,after);}
public PeopleFilter withQ(String value){return new PeopleFilter(workspaceId,value,limit,after);}
public PeopleFilter withLimit(Integer value){return new PeopleFilter(workspaceId,q,value,after);}
public PeopleFilter withAfter(String value){return new PeopleFilter(workspaceId,q,limit,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(q!=null)options=options.query("q",String.valueOf(q));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(after!=null)options=options.query("after",String.valueOf(after));
return options;}
}

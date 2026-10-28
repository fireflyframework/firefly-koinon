// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record IdentityFilter(String q,String kind,String status,Integer page,Integer pageSize) {
public static IdentityFilter empty(){return new IdentityFilter(null,null,null,null,null);}
public IdentityFilter withQ(String value){return new IdentityFilter(value,kind,status,page,pageSize);}
public IdentityFilter withKind(String value){return new IdentityFilter(q,value,status,page,pageSize);}
public IdentityFilter withStatus(String value){return new IdentityFilter(q,kind,value,page,pageSize);}
public IdentityFilter withPage(Integer value){return new IdentityFilter(q,kind,status,value,pageSize);}
public IdentityFilter withPageSize(Integer value){return new IdentityFilter(q,kind,status,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(kind!=null)options=options.query("kind",String.valueOf(kind));
if(status!=null)options=options.query("status",String.valueOf(status));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

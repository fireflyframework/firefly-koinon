// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record ShareFilter(String q,String status,Integer page,Integer pageSize) {
public static ShareFilter empty(){return new ShareFilter(null,null,null,null);}
public ShareFilter withQ(String value){return new ShareFilter(value,status,page,pageSize);}
public ShareFilter withStatus(String value){return new ShareFilter(q,value,page,pageSize);}
public ShareFilter withPage(Integer value){return new ShareFilter(q,status,value,pageSize);}
public ShareFilter withPageSize(Integer value){return new ShareFilter(q,status,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",String.valueOf(status));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

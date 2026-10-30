// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record McpOAuthClientFilter(String q,McpOAuthClientStatus status,Integer page,Integer pageSize,McpOAuthClientSort sort,McpOAuthClientOrder order) {
public static McpOAuthClientFilter empty(){return new McpOAuthClientFilter(null,null,null,null,null,null);}
public McpOAuthClientFilter withQ(String value){return new McpOAuthClientFilter(value,status,page,pageSize,sort,order);}
public McpOAuthClientFilter withStatus(McpOAuthClientStatus value){return new McpOAuthClientFilter(q,value,page,pageSize,sort,order);}
public McpOAuthClientFilter withPage(Integer value){return new McpOAuthClientFilter(q,status,value,pageSize,sort,order);}
public McpOAuthClientFilter withPageSize(Integer value){return new McpOAuthClientFilter(q,status,page,value,sort,order);}
public McpOAuthClientFilter withSort(McpOAuthClientSort value){return new McpOAuthClientFilter(q,status,page,pageSize,value,order);}
public McpOAuthClientFilter withOrder(McpOAuthClientOrder value){return new McpOAuthClientFilter(q,status,page,pageSize,sort,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",status.value());
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(sort!=null)options=options.query("sort",sort.value());
if(order!=null)options=options.query("order",order.value());
return options;}
}

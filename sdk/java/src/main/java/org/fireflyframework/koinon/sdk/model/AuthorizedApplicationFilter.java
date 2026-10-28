// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record AuthorizedApplicationFilter(String q,String status,Integer page,Integer pageSize,String sort,String order) {
public static AuthorizedApplicationFilter empty(){return new AuthorizedApplicationFilter(null,null,null,null,null,null);}
public AuthorizedApplicationFilter withQ(String value){return new AuthorizedApplicationFilter(value,status,page,pageSize,sort,order);}
public AuthorizedApplicationFilter withStatus(String value){return new AuthorizedApplicationFilter(q,value,page,pageSize,sort,order);}
public AuthorizedApplicationFilter withPage(Integer value){return new AuthorizedApplicationFilter(q,status,value,pageSize,sort,order);}
public AuthorizedApplicationFilter withPageSize(Integer value){return new AuthorizedApplicationFilter(q,status,page,value,sort,order);}
public AuthorizedApplicationFilter withSort(String value){return new AuthorizedApplicationFilter(q,status,page,pageSize,value,order);}
public AuthorizedApplicationFilter withOrder(String value){return new AuthorizedApplicationFilter(q,status,page,pageSize,sort,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",String.valueOf(status));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(sort!=null)options=options.query("sort",String.valueOf(sort));
if(order!=null)options=options.query("order",String.valueOf(order));
return options;}
}

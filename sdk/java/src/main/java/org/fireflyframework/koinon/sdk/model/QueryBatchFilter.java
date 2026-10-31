// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record QueryBatchFilter(Integer page,Integer pageSize) {
public static QueryBatchFilter empty(){return new QueryBatchFilter(null,null);}
public QueryBatchFilter withPage(Integer value){return new QueryBatchFilter(value,pageSize);}
public QueryBatchFilter withPageSize(Integer value){return new QueryBatchFilter(page,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

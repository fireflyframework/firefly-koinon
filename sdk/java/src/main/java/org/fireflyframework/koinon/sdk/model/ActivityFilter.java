// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record ActivityFilter(Integer page,Integer pageSize) {
public static ActivityFilter empty(){return new ActivityFilter(null,null);}
public ActivityFilter withPage(Integer value){return new ActivityFilter(value,pageSize);}
public ActivityFilter withPageSize(Integer value){return new ActivityFilter(page,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

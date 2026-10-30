// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record DocumentHistoryFilter(Integer page,Integer pageSize) {
public static DocumentHistoryFilter empty(){return new DocumentHistoryFilter(null,null);}
public DocumentHistoryFilter withPage(Integer value){return new DocumentHistoryFilter(value,pageSize);}
public DocumentHistoryFilter withPageSize(Integer value){return new DocumentHistoryFilter(page,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

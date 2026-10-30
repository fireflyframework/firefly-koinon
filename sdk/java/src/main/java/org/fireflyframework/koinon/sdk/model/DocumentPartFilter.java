// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record DocumentPartFilter(String kind,Integer page,Integer pageSize) {
public static DocumentPartFilter empty(){return new DocumentPartFilter(null,null,null);}
public DocumentPartFilter withKind(String value){return new DocumentPartFilter(value,page,pageSize);}
public DocumentPartFilter withPage(Integer value){return new DocumentPartFilter(kind,value,pageSize);}
public DocumentPartFilter withPageSize(Integer value){return new DocumentPartFilter(kind,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(kind!=null)options=options.query("kind",String.valueOf(kind));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

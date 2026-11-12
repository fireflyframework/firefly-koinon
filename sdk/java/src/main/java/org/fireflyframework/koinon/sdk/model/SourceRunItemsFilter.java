// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceRunItemsFilter(Integer limit,String cursor) {
public static SourceRunItemsFilter empty(){return new SourceRunItemsFilter(null,null);}
public SourceRunItemsFilter withLimit(Integer value){return new SourceRunItemsFilter(value,cursor);}
public SourceRunItemsFilter withCursor(String value){return new SourceRunItemsFilter(limit,value);}
public RequestOptions applyTo(RequestOptions options){
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}

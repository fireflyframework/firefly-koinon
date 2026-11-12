// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceItemsFilter(Integer limit,String cursor) {
public static SourceItemsFilter empty(){return new SourceItemsFilter(null,null);}
public SourceItemsFilter withLimit(Integer value){return new SourceItemsFilter(value,cursor);}
public SourceItemsFilter withCursor(String value){return new SourceItemsFilter(limit,value);}
public RequestOptions applyTo(RequestOptions options){
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}

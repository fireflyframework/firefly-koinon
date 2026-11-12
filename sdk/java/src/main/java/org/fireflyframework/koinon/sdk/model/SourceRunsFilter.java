// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceRunsFilter(Integer limit,String cursor) {
public static SourceRunsFilter empty(){return new SourceRunsFilter(null,null);}
public SourceRunsFilter withLimit(Integer value){return new SourceRunsFilter(value,cursor);}
public SourceRunsFilter withCursor(String value){return new SourceRunsFilter(limit,value);}
public RequestOptions applyTo(RequestOptions options){
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}

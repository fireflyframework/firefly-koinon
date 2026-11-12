// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceConnectionFilter(String cursor,Integer limit) {
public static SourceConnectionFilter empty(){return new SourceConnectionFilter(null,null);}
public SourceConnectionFilter withCursor(String value){return new SourceConnectionFilter(value,limit);}
public SourceConnectionFilter withLimit(Integer value){return new SourceConnectionFilter(cursor,value);}
public RequestOptions applyTo(RequestOptions options){
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
return options;}
}

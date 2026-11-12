// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceMappingsPageFilter(Integer limit,String cursor) {
public static SourceMappingsPageFilter empty(){return new SourceMappingsPageFilter(null,null);}
public SourceMappingsPageFilter withLimit(Integer value){return new SourceMappingsPageFilter(value,cursor);}
public SourceMappingsPageFilter withCursor(String value){return new SourceMappingsPageFilter(limit,value);}
public RequestOptions applyTo(RequestOptions options){
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}

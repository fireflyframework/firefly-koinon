// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceValidationItemsFilter(String cursor,Integer limit) {
public static SourceValidationItemsFilter empty(){return new SourceValidationItemsFilter(null,null);}
public SourceValidationItemsFilter withCursor(String value){return new SourceValidationItemsFilter(value,limit);}
public SourceValidationItemsFilter withLimit(Integer value){return new SourceValidationItemsFilter(cursor,value);}
public RequestOptions applyTo(RequestOptions options){
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
return options;}
}

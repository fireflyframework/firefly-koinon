// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record MessageFilter(String before,Integer limit) {
public static MessageFilter empty(){return new MessageFilter(null,null);}
public MessageFilter withBefore(String value){return new MessageFilter(value,limit);}
public MessageFilter withLimit(Integer value){return new MessageFilter(before,value);}
public RequestOptions applyTo(RequestOptions options){
if(before!=null)options=options.query("before",String.valueOf(before));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
return options;}
}

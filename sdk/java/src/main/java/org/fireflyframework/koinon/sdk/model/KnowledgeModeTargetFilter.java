// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record KnowledgeModeTargetFilter(String after,Integer limit) {
public static KnowledgeModeTargetFilter empty(){return new KnowledgeModeTargetFilter(null,null);}
public KnowledgeModeTargetFilter withAfter(String value){return new KnowledgeModeTargetFilter(value,limit);}
public KnowledgeModeTargetFilter withLimit(Integer value){return new KnowledgeModeTargetFilter(after,value);}
public RequestOptions applyTo(RequestOptions options){
if(after!=null)options=options.query("after",String.valueOf(after));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
return options;}
}

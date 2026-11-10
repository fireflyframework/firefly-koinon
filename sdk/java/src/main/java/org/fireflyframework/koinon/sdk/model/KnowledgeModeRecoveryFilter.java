// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record KnowledgeModeRecoveryFilter(String after,Integer limit) {
public static KnowledgeModeRecoveryFilter empty(){return new KnowledgeModeRecoveryFilter(null,null);}
public KnowledgeModeRecoveryFilter withAfter(String value){return new KnowledgeModeRecoveryFilter(value,limit);}
public KnowledgeModeRecoveryFilter withLimit(Integer value){return new KnowledgeModeRecoveryFilter(after,value);}
public RequestOptions applyTo(RequestOptions options){
if(after!=null)options=options.query("after",String.valueOf(after));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
return options;}
}

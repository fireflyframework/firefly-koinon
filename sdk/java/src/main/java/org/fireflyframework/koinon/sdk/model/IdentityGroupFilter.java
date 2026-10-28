// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record IdentityGroupFilter(String q,Integer limit,String after) {
public static IdentityGroupFilter empty(){return new IdentityGroupFilter(null,null,null);}
public IdentityGroupFilter withQ(String value){return new IdentityGroupFilter(value,limit,after);}
public IdentityGroupFilter withLimit(Integer value){return new IdentityGroupFilter(q,value,after);}
public IdentityGroupFilter withAfter(String value){return new IdentityGroupFilter(q,limit,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(after!=null)options=options.query("after",String.valueOf(after));
return options;}
}

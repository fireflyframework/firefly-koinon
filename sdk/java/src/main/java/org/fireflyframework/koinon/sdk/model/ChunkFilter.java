// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record ChunkFilter(Integer offset,Integer limit,Integer page,String section,String q) {
public static ChunkFilter empty(){return new ChunkFilter(null,null,null,null,null);}
public ChunkFilter withOffset(Integer value){return new ChunkFilter(value,limit,page,section,q);}
public ChunkFilter withLimit(Integer value){return new ChunkFilter(offset,value,page,section,q);}
public ChunkFilter withPage(Integer value){return new ChunkFilter(offset,limit,value,section,q);}
public ChunkFilter withSection(String value){return new ChunkFilter(offset,limit,page,value,q);}
public ChunkFilter withQ(String value){return new ChunkFilter(offset,limit,page,section,value);}
public RequestOptions applyTo(RequestOptions options){
if(offset!=null)options=options.query("offset",String.valueOf(offset));
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(page!=null)options=options.query("page",String.valueOf(page));
if(section!=null)options=options.query("section",String.valueOf(section));
if(q!=null)options=options.query("q",String.valueOf(q));
return options;}
}

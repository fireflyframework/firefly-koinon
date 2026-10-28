// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record AttachmentChunkFilter(Integer page,Integer pageSize,String q) {
public static AttachmentChunkFilter empty(){return new AttachmentChunkFilter(null,null,null);}
public AttachmentChunkFilter withPage(Integer value){return new AttachmentChunkFilter(value,pageSize,q);}
public AttachmentChunkFilter withPageSize(Integer value){return new AttachmentChunkFilter(page,value,q);}
public AttachmentChunkFilter withQ(String value){return new AttachmentChunkFilter(page,pageSize,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(q!=null)options=options.query("q",String.valueOf(q));
return options;}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record AttachmentFilter(Integer page,Integer pageSize,String q,String status,String kind) {
public static AttachmentFilter empty(){return new AttachmentFilter(null,null,null,null,null);}
public AttachmentFilter withPage(Integer value){return new AttachmentFilter(value,pageSize,q,status,kind);}
public AttachmentFilter withPageSize(Integer value){return new AttachmentFilter(page,value,q,status,kind);}
public AttachmentFilter withQ(String value){return new AttachmentFilter(page,pageSize,value,status,kind);}
public AttachmentFilter withStatus(String value){return new AttachmentFilter(page,pageSize,q,value,kind);}
public AttachmentFilter withKind(String value){return new AttachmentFilter(page,pageSize,q,status,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",String.valueOf(status));
if(kind!=null)options=options.query("kind",String.valueOf(kind));
return options;}
}

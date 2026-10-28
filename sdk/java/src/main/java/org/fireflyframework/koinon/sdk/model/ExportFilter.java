// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record ExportFilter(String q,String status,Integer page,Integer pageSize) {
public static ExportFilter empty(){return new ExportFilter(null,null,null,null);}
public ExportFilter withQ(String value){return new ExportFilter(value,status,page,pageSize);}
public ExportFilter withStatus(String value){return new ExportFilter(q,value,page,pageSize);}
public ExportFilter withPage(Integer value){return new ExportFilter(q,status,value,pageSize);}
public ExportFilter withPageSize(Integer value){return new ExportFilter(q,status,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(status!=null)options=options.query("status",String.valueOf(status));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

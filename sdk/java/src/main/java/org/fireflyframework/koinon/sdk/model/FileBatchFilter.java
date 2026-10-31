// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record FileBatchFilter(Integer page,Integer pageSize) {
public static FileBatchFilter empty(){return new FileBatchFilter(null,null);}
public FileBatchFilter withPage(Integer value){return new FileBatchFilter(value,pageSize);}
public FileBatchFilter withPageSize(Integer value){return new FileBatchFilter(page,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record TableSnapshotFilter(Integer page,Integer pageSize) {
public static TableSnapshotFilter empty(){return new TableSnapshotFilter(null,null);}
public TableSnapshotFilter withPage(Integer value){return new TableSnapshotFilter(value,pageSize);}
public TableSnapshotFilter withPageSize(Integer value){return new TableSnapshotFilter(page,value);}
public RequestOptions applyTo(RequestOptions options){
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

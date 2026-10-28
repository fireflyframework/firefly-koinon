// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record TableCoordinatePageFilter(String snapshotId,Integer page,Integer pageSize) {
public static TableCoordinatePageFilter empty(){return new TableCoordinatePageFilter(null,null,null);}
public TableCoordinatePageFilter withSnapshotId(String value){return new TableCoordinatePageFilter(value,page,pageSize);}
public TableCoordinatePageFilter withPage(Integer value){return new TableCoordinatePageFilter(snapshotId,value,pageSize);}
public TableCoordinatePageFilter withPageSize(Integer value){return new TableCoordinatePageFilter(snapshotId,page,value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(snapshotId,"snapshot_id is required");
if(snapshotId!=null)options=options.query("snapshot_id",String.valueOf(snapshotId));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

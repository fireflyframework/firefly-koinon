// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceDriveFilter(String siteId,String cursor) {
public static SourceDriveFilter empty(){return new SourceDriveFilter(null,null);}
public SourceDriveFilter withSiteId(String value){return new SourceDriveFilter(value,cursor);}
public SourceDriveFilter withCursor(String value){return new SourceDriveFilter(siteId,value);}
public RequestOptions applyTo(RequestOptions options){
if(siteId!=null)options=options.query("site_id",String.valueOf(siteId));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}

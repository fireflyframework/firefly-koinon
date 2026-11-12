// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceSiteFilter(String q,String cursor) {
public static SourceSiteFilter empty(){return new SourceSiteFilter(null,null);}
public SourceSiteFilter withQ(String value){return new SourceSiteFilter(value,cursor);}
public SourceSiteFilter withCursor(String value){return new SourceSiteFilter(q,value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(q,"q is required");
if(q!=null)options=options.query("q",String.valueOf(q));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}

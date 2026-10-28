// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record LineageFilter(String assetId) {
public static LineageFilter empty(){return new LineageFilter(null);}
public LineageFilter withAssetId(String value){return new LineageFilter(value);}
public RequestOptions applyTo(RequestOptions options){
if(assetId!=null)options=options.query("asset_id",String.valueOf(assetId));
return options;}
}

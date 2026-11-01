// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record CatalogLifecycleFilter(String expectedUpdatedAt) {
public static CatalogLifecycleFilter empty(){return new CatalogLifecycleFilter(null);}
public CatalogLifecycleFilter withExpectedUpdatedAt(String value){return new CatalogLifecycleFilter(value);}
public RequestOptions applyTo(RequestOptions options){
if(expectedUpdatedAt!=null)options=options.query("expected_updated_at",String.valueOf(expectedUpdatedAt));
return options;}
}

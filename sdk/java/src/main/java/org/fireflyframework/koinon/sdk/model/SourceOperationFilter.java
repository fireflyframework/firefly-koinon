// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceOperationFilter(String action) {
public static SourceOperationFilter empty(){return new SourceOperationFilter(null);}
public SourceOperationFilter withAction(String value){return new SourceOperationFilter(value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(action,"action is required");
if(action!=null)options=options.query("action",String.valueOf(action));
return options;}
}

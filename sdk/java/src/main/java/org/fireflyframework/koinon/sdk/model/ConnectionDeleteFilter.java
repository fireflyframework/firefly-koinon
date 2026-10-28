// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record ConnectionDeleteFilter(Integer expectedRevision) {
public static ConnectionDeleteFilter empty(){return new ConnectionDeleteFilter(null);}
public ConnectionDeleteFilter withExpectedRevision(Integer value){return new ConnectionDeleteFilter(value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(expectedRevision,"expected_revision is required");
if(expectedRevision!=null)options=options.query("expected_revision",String.valueOf(expectedRevision));
return options;}
}

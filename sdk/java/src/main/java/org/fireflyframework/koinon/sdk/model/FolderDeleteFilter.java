// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record FolderDeleteFilter(Integer expectedRevision) {
public static FolderDeleteFilter empty(){return new FolderDeleteFilter(null);}
public FolderDeleteFilter withExpectedRevision(Integer value){return new FolderDeleteFilter(value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(expectedRevision,"expected_revision is required");
if(expectedRevision!=null)options=options.query("expected_revision",String.valueOf(expectedRevision));
return options;}
}

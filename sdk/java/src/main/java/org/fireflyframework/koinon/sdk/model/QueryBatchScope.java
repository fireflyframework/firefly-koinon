// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record QueryBatchScope(String workspaceId) {
public static QueryBatchScope empty(){return new QueryBatchScope(null);}
public QueryBatchScope withWorkspaceId(String value){return new QueryBatchScope(value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(workspaceId,"workspace_id is required");
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
return options;}
}

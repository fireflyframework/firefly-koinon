// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record WorkspaceFilter(String workspaceId) {
public static WorkspaceFilter empty(){return new WorkspaceFilter(null);}
public WorkspaceFilter withWorkspaceId(String value){return new WorkspaceFilter(value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
return options;}
}

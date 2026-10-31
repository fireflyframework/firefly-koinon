// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record OrganizationScopeFilter(String workspaceId) {
public static OrganizationScopeFilter empty(){return new OrganizationScopeFilter(null);}
public OrganizationScopeFilter withWorkspaceId(String value){return new OrganizationScopeFilter(value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
return options;}
}

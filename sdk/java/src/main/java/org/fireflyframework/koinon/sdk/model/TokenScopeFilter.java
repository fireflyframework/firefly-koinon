// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record TokenScopeFilter(String tenantId,String workspaceId) {
public static TokenScopeFilter empty(){return new TokenScopeFilter(null,null);}
public TokenScopeFilter withTenantId(String value){return new TokenScopeFilter(value,workspaceId);}
public TokenScopeFilter withWorkspaceId(String value){return new TokenScopeFilter(tenantId,value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(tenantId,"tenant_id is required");
if(tenantId!=null)options=options.query("tenant_id",String.valueOf(tenantId));
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
return options;}
}

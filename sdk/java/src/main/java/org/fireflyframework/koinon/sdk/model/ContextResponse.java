// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;



/** Typed canonical ContextResponse contract. */
public record ContextResponse(
    @JsonProperty("workspace_permissions") Map<String,List<String>> workspacePermissions,
    @JsonProperty("subject") String subject,
    @JsonProperty("tenants") List<TenantContext> tenants,
    @JsonProperty("memberships") List<Membership> memberships,
    @JsonProperty("workspaces") List<CatalogEntry> workspaces
) {
    public ContextResponse {
        workspacePermissions=workspacePermissions==null?null:Map.copyOf(workspacePermissions);
        tenants=tenants==null?null:List.copyOf(tenants);
        memberships=memberships==null?null:List.copyOf(memberships);
        workspaces=workspaces==null?null:List.copyOf(workspaces);
    }

}

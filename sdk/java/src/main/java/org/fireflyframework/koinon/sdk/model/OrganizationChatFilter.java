// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record OrganizationChatFilter(String workspaceId,String projectId) {
public static OrganizationChatFilter empty(){return new OrganizationChatFilter(null,null);}
public OrganizationChatFilter withWorkspaceId(String value){return new OrganizationChatFilter(value,projectId);}
public OrganizationChatFilter withProjectId(String value){return new OrganizationChatFilter(workspaceId,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(projectId!=null)options=options.query("project_id",String.valueOf(projectId));
return options;}
}

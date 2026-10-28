// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record IndexScope(String workspaceId,KnowledgeDomain domain) {
public static IndexScope empty(){return new IndexScope(null,null);}
public IndexScope withWorkspaceId(String value){return new IndexScope(value,domain);}
public IndexScope withDomain(KnowledgeDomain value){return new IndexScope(workspaceId,value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(workspaceId,"workspace_id is required");
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
Objects.requireNonNull(domain,"domain is required");
if(domain!=null)options=options.query("domain",domain.value());
return options;}
}

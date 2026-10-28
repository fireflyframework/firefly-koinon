// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record IndexFilter(String workspaceId,KnowledgeDomain domain,Integer limit,Integer offset,String status,Integer dimensions,String modelId,String providerKind) {
public static IndexFilter empty(){return new IndexFilter(null,null,null,null,null,null,null,null);}
public IndexFilter withWorkspaceId(String value){return new IndexFilter(value,domain,limit,offset,status,dimensions,modelId,providerKind);}
public IndexFilter withDomain(KnowledgeDomain value){return new IndexFilter(workspaceId,value,limit,offset,status,dimensions,modelId,providerKind);}
public IndexFilter withLimit(Integer value){return new IndexFilter(workspaceId,domain,value,offset,status,dimensions,modelId,providerKind);}
public IndexFilter withOffset(Integer value){return new IndexFilter(workspaceId,domain,limit,value,status,dimensions,modelId,providerKind);}
public IndexFilter withStatus(String value){return new IndexFilter(workspaceId,domain,limit,offset,value,dimensions,modelId,providerKind);}
public IndexFilter withDimensions(Integer value){return new IndexFilter(workspaceId,domain,limit,offset,status,value,modelId,providerKind);}
public IndexFilter withModelId(String value){return new IndexFilter(workspaceId,domain,limit,offset,status,dimensions,value,providerKind);}
public IndexFilter withProviderKind(String value){return new IndexFilter(workspaceId,domain,limit,offset,status,dimensions,modelId,value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(workspaceId,"workspace_id is required");
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
Objects.requireNonNull(domain,"domain is required");
if(domain!=null)options=options.query("domain",domain.value());
if(limit!=null)options=options.query("limit",String.valueOf(limit));
if(offset!=null)options=options.query("offset",String.valueOf(offset));
if(status!=null)options=options.query("status",String.valueOf(status));
if(dimensions!=null)options=options.query("dimensions",String.valueOf(dimensions));
if(modelId!=null)options=options.query("model_id",String.valueOf(modelId));
if(providerKind!=null)options=options.query("provider_kind",String.valueOf(providerKind));
return options;}
}

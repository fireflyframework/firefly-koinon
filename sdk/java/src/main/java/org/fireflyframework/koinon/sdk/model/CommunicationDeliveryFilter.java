// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record CommunicationDeliveryFilter(String workspaceId,String status,String kind,String channel,String createdFrom,String createdTo,Integer page,Integer pageSize) {
public static CommunicationDeliveryFilter empty(){return new CommunicationDeliveryFilter(null,null,null,null,null,null,null,null);}
public CommunicationDeliveryFilter withWorkspaceId(String value){return new CommunicationDeliveryFilter(value,status,kind,channel,createdFrom,createdTo,page,pageSize);}
public CommunicationDeliveryFilter withStatus(String value){return new CommunicationDeliveryFilter(workspaceId,value,kind,channel,createdFrom,createdTo,page,pageSize);}
public CommunicationDeliveryFilter withKind(String value){return new CommunicationDeliveryFilter(workspaceId,status,value,channel,createdFrom,createdTo,page,pageSize);}
public CommunicationDeliveryFilter withChannel(String value){return new CommunicationDeliveryFilter(workspaceId,status,kind,value,createdFrom,createdTo,page,pageSize);}
public CommunicationDeliveryFilter withCreatedFrom(String value){return new CommunicationDeliveryFilter(workspaceId,status,kind,channel,value,createdTo,page,pageSize);}
public CommunicationDeliveryFilter withCreatedTo(String value){return new CommunicationDeliveryFilter(workspaceId,status,kind,channel,createdFrom,value,page,pageSize);}
public CommunicationDeliveryFilter withPage(Integer value){return new CommunicationDeliveryFilter(workspaceId,status,kind,channel,createdFrom,createdTo,value,pageSize);}
public CommunicationDeliveryFilter withPageSize(Integer value){return new CommunicationDeliveryFilter(workspaceId,status,kind,channel,createdFrom,createdTo,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(status!=null)options=options.query("status",String.valueOf(status));
if(kind!=null)options=options.query("kind",String.valueOf(kind));
if(channel!=null)options=options.query("channel",String.valueOf(channel));
if(createdFrom!=null)options=options.query("created_from",String.valueOf(createdFrom));
if(createdTo!=null)options=options.query("created_to",String.valueOf(createdTo));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

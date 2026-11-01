// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record NotificationFilter(String tenantId,String kind,String read,Integer page,Integer pageSize) {
public static NotificationFilter empty(){return new NotificationFilter(null,null,null,null,null);}
public NotificationFilter withTenantId(String value){return new NotificationFilter(value,kind,read,page,pageSize);}
public NotificationFilter withKind(String value){return new NotificationFilter(tenantId,value,read,page,pageSize);}
public NotificationFilter withRead(String value){return new NotificationFilter(tenantId,kind,value,page,pageSize);}
public NotificationFilter withPage(Integer value){return new NotificationFilter(tenantId,kind,read,value,pageSize);}
public NotificationFilter withPageSize(Integer value){return new NotificationFilter(tenantId,kind,read,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(tenantId!=null)options=options.query("tenant_id",String.valueOf(tenantId));
if(kind!=null)options=options.query("kind",String.valueOf(kind));
if(read!=null)options=options.query("read",String.valueOf(read));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

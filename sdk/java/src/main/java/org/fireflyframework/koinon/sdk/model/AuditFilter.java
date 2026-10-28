// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record AuditFilter(String q,String action,String subject,String fromDate,String throughDate,String timeZone,Integer page,Integer pageSize,String sort,String order) {
public static AuditFilter empty(){return new AuditFilter(null,null,null,null,null,null,null,null,null,null);}
public AuditFilter withQ(String value){return new AuditFilter(value,action,subject,fromDate,throughDate,timeZone,page,pageSize,sort,order);}
public AuditFilter withAction(String value){return new AuditFilter(q,value,subject,fromDate,throughDate,timeZone,page,pageSize,sort,order);}
public AuditFilter withSubject(String value){return new AuditFilter(q,action,value,fromDate,throughDate,timeZone,page,pageSize,sort,order);}
public AuditFilter withFromDate(String value){return new AuditFilter(q,action,subject,value,throughDate,timeZone,page,pageSize,sort,order);}
public AuditFilter withThroughDate(String value){return new AuditFilter(q,action,subject,fromDate,value,timeZone,page,pageSize,sort,order);}
public AuditFilter withTimeZone(String value){return new AuditFilter(q,action,subject,fromDate,throughDate,value,page,pageSize,sort,order);}
public AuditFilter withPage(Integer value){return new AuditFilter(q,action,subject,fromDate,throughDate,timeZone,value,pageSize,sort,order);}
public AuditFilter withPageSize(Integer value){return new AuditFilter(q,action,subject,fromDate,throughDate,timeZone,page,value,sort,order);}
public AuditFilter withSort(String value){return new AuditFilter(q,action,subject,fromDate,throughDate,timeZone,page,pageSize,value,order);}
public AuditFilter withOrder(String value){return new AuditFilter(q,action,subject,fromDate,throughDate,timeZone,page,pageSize,sort,value);}
public RequestOptions applyTo(RequestOptions options){
if(q!=null)options=options.query("q",String.valueOf(q));
if(action!=null)options=options.query("action",String.valueOf(action));
if(subject!=null)options=options.query("subject",String.valueOf(subject));
if(fromDate!=null)options=options.query("from_date",String.valueOf(fromDate));
if(throughDate!=null)options=options.query("through_date",String.valueOf(throughDate));
if(timeZone!=null)options=options.query("time_zone",String.valueOf(timeZone));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
if(sort!=null)options=options.query("sort",String.valueOf(sort));
if(order!=null)options=options.query("order",String.valueOf(order));
return options;}
}

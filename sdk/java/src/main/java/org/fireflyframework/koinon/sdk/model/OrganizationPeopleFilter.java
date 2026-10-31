// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record OrganizationPeopleFilter(String workspaceId,String q,String jobTitle,String unitId,String departmentId,String managerId,Boolean unassigned,Integer page,Integer pageSize) {
public static OrganizationPeopleFilter empty(){return new OrganizationPeopleFilter(null,null,null,null,null,null,null,null,null);}
public OrganizationPeopleFilter withWorkspaceId(String value){return new OrganizationPeopleFilter(value,q,jobTitle,unitId,departmentId,managerId,unassigned,page,pageSize);}
public OrganizationPeopleFilter withQ(String value){return new OrganizationPeopleFilter(workspaceId,value,jobTitle,unitId,departmentId,managerId,unassigned,page,pageSize);}
public OrganizationPeopleFilter withJobTitle(String value){return new OrganizationPeopleFilter(workspaceId,q,value,unitId,departmentId,managerId,unassigned,page,pageSize);}
public OrganizationPeopleFilter withUnitId(String value){return new OrganizationPeopleFilter(workspaceId,q,jobTitle,value,departmentId,managerId,unassigned,page,pageSize);}
public OrganizationPeopleFilter withDepartmentId(String value){return new OrganizationPeopleFilter(workspaceId,q,jobTitle,unitId,value,managerId,unassigned,page,pageSize);}
public OrganizationPeopleFilter withManagerId(String value){return new OrganizationPeopleFilter(workspaceId,q,jobTitle,unitId,departmentId,value,unassigned,page,pageSize);}
public OrganizationPeopleFilter withUnassigned(Boolean value){return new OrganizationPeopleFilter(workspaceId,q,jobTitle,unitId,departmentId,managerId,value,page,pageSize);}
public OrganizationPeopleFilter withPage(Integer value){return new OrganizationPeopleFilter(workspaceId,q,jobTitle,unitId,departmentId,managerId,unassigned,value,pageSize);}
public OrganizationPeopleFilter withPageSize(Integer value){return new OrganizationPeopleFilter(workspaceId,q,jobTitle,unitId,departmentId,managerId,unassigned,page,value);}
public RequestOptions applyTo(RequestOptions options){
if(workspaceId!=null)options=options.query("workspace_id",String.valueOf(workspaceId));
if(q!=null)options=options.query("q",String.valueOf(q));
if(jobTitle!=null)options=options.query("job_title",String.valueOf(jobTitle));
if(unitId!=null)options=options.query("unit_id",String.valueOf(unitId));
if(departmentId!=null)options=options.query("department_id",String.valueOf(departmentId));
if(managerId!=null)options=options.query("manager_id",String.valueOf(managerId));
if(unassigned!=null)options=options.query("unassigned",String.valueOf(unassigned));
if(page!=null)options=options.query("page",String.valueOf(page));
if(pageSize!=null)options=options.query("page_size",String.valueOf(pageSize));
return options;}
}

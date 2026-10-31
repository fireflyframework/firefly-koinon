// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {
 KoinonClient, OrganizationPerson, OrganizationPersonPatch,
 OrganizationUnitInput, OrganizationPeopleFilter,
} from '../src/index.js';

declare const client:KoinonClient;
const filter:OrganizationPeopleFilter={workspace_id:'workspace',unassigned:false,page_size:25};
const page=client.organizationPeople.list('organization',filter);
const person:Promise<OrganizationPerson>=client.organizationPeople.me('organization');
const patch:OrganizationPersonPatch={expected_revision:1,manager_id:null};
const unit:OrganizationUnitInput={name:'Engineering',kind:'department'};
void page;void person;void patch;void unit;
// @ts-expect-error Positions cannot change access roles.
const invalid:OrganizationPersonPatch={expected_revision:1,roles:['admin']};
// @ts-expect-error Unknown directory filters are not part of the public API.
client.organizationPeople.list('organization',{include_private_workspaces:true});
// @ts-expect-error Revision checks are required for organization edits.
client.organizationPeople.update('organization','person',{job_title:'Engineer'});
void invalid;

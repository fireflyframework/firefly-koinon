// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {KoinonClient,OrganizationPresentation,OrganizationPresentationInput,CorporateProfileRefreshInput} from '../src/index.js';
declare const client:KoinonClient;
const presentation:Promise<OrganizationPresentation>=client.corporateProfiles.presentation('tenant');
const input:OrganizationPresentationInput={expected_revision:3,name_mode:'organization'};
const refresh:CorporateProfileRefreshInput={};
void presentation;void input;void refresh;
// @ts-expect-error A presentation preference cannot be cleared with null.
const invalid:OrganizationPresentationInput={expected_revision:3,name_mode:null};
// @ts-expect-error Refresh resolves the current provider binding on the server.
client.corporateProfiles.refreshSelf('tenant',{upstream_user_id:'other'});
// @ts-expect-error Preference writes require the observed revision.
client.corporateProfiles.updatePresentation('tenant',{name_mode:'personal'});
void invalid;

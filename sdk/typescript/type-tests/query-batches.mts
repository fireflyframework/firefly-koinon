// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {KoinonClient,type QueryBatchCreate,type QueryBatchAction} from '../src/index.js';
declare const client:KoinonClient;
const manifest:QueryBatchCreate={workspace_id:'w',items:[{client_item_id:'one',dataset_id:'d',question:'Count'}]};
const action:QueryBatchAction={expected_revision:2};
void client.queryBatches.create('north',manifest,'stable');
void client.queryBatches.reconcile('north','batch','item',action,'inspect');
// @ts-expect-error Caller supplies the admission key; model work is never retried implicitly.
void client.queryBatches.create('north',manifest);
// @ts-expect-error Query batch revisions are explicit and non-null.
void client.queryBatches.cancel('north','batch',{expected_revision:null},'cancel');
// @ts-expect-error Independent NL queries do not accept authored SQL.
const sql:QueryBatchCreate={workspace_id:'w',items:[{client_item_id:'one',dataset_id:'d',question:'Count',sql:'SELECT 1'}]};
void sql;

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {KoinonClient,type FileBatchCreate,type BulkAction} from '../src/index.js';
declare const client:KoinonClient;
const action:BulkAction={expected_revision:2};
const manifest:FileBatchCreate={destination:{workspace_id:'w',project_id:'p',parent_id:'c'},items:[{client_item_id:'one',filename:'facts.csv',mode:'dataset',size_bytes:8,sha256:'a'.repeat(64)}]};
void client.fileBatches.create('north',manifest,'stable-key');
void client.fileBatches.submit('north','batch',action,'submit-key');
void client.fileBatches.upload('north','batch','item',new Blob(['original']),'upload-key');
// @ts-expect-error Caller supplies an idempotency key for raw original uploads.
void client.fileBatches.upload('north','batch','item',new Blob(['original']));
// @ts-expect-error Admission is a typed manifest rather than a JSON-shaped arbitrary object.
void client.fileBatches.create('north',{items:[]},'key');
// @ts-expect-error The bounded intake API does not advertise query batch support.
const invalid:FileBatchCreate={destination:{workspace_id:'w',project_id:'p',parent_id:'c'},items:[{client_item_id:'q',filename:'q',mode:'query',size_bytes:1,sha256:'a'.repeat(64)}]};
void invalid;

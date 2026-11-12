// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {RunInput, SearchHit, SourceReference} from '../src/index.js';
declare const hit: SearchHit;
const reference: SourceReference | null | undefined = hit.source_reference;
const legacy: SearchHit = {id:'projection',title:'Recorded',text:'retained',asset_id:'document'};
void reference;
void legacy;
const localRun:RunInput={agent_id:'agent',message:'Question',client_request_id:'request',reader_source_connections:[]};
const selectedRun:RunInput={...localRun,reader_source_connections:[{provider:'google_drive',connection_id:'reader'}]};
void localRun;void selectedRun;

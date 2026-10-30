// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {SearchHit, SourceReference} from '../src/index.js';
declare const hit: SearchHit;
const reference: SourceReference | null | undefined = hit.source_reference;
const legacy: SearchHit = {id:'projection',title:'Recorded',text:'retained',asset_id:'document'};
void reference;
void legacy;

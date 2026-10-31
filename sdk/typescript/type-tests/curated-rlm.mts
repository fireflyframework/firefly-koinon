// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {RlmToolReceipt,DocumentKnowledgeCapabilities} from '../dist/index.js';
declare const receipt:RlmToolReceipt;
const itemIds:ReadonlyArray<string>=receipt.knowledge_item_ids??[];
const documentIds:ReadonlyArray<string>=receipt.source_ids??[];
void itemIds;void documentIds;
// @ts-expect-error Curated identifiers are strings, never untyped values.
const invalid:RlmToolReceipt={...receipt,knowledge_item_ids:[42]};
declare const capabilities:DocumentKnowledgeCapabilities;
const qualified:DocumentKnowledgeCapabilities={...capabilities,rlm_curated_knowledge_supported:true,rlm_curated_knowledge_reason:null};
void invalid;void qualified;

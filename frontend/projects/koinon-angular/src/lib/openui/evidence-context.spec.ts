// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {TestBed} from '@angular/core/testing';
import {KoinonEvidenceContext} from '../../../chat/evidence/src/openui/evidence-context';
import type {EvidenceResult} from '@fireflyframework/koinon-sdk';
describe('authorized evidence resolution',()=>{
 beforeEach(()=>TestBed.configureTestingModule({providers:[KoinonEvidenceContext]}));
 it('rejects another run before showing its data',async()=>{const c=TestBed.inject(KoinonEvidenceContext);c.bind('trusted',async()=>({id:'r',run_id:'other',kind:'query',data:{query_id:'q',execution_status:'OK'}}),'tenant');await expect(c.read('r')).rejects.toThrow('different answer');});
 it('discards a response after host context changes',async()=>{const c=TestBed.inject(KoinonEvidenceContext);let resolve!:(v:EvidenceResult)=>void;c.bind('run',()=>new Promise(r=>resolve=r),'one');const pending=c.read('r');c.bind('run',async()=>({id:'r',run_id:'run',kind:'lineage',data:{nodes:[],edges:[]}}),'two');resolve({id:'r',run_id:'run',kind:'query',data:{query_id:'q',execution_status:'OK'}});await expect(pending).rejects.toMatchObject({name:'AbortError'});});
 it('preserves access denial without sample data',async()=>{const c=TestBed.inject(KoinonEvidenceContext);c.bind('run',async()=>{throw new Error('Source no longer accessible');},'tenant');await expect(c.read('r')).rejects.toThrow('no longer accessible');});
});

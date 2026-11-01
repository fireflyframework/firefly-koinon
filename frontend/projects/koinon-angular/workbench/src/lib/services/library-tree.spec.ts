// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { describe, expect, it } from 'vitest';
import type { CatalogEntry, ResourceKind } from '@fireflyframework/koinon-sdk';
import { childrenOf, folderTrail, nextFolderKind } from './library-tree';
function entry(id: string, kind: ResourceKind, parent: string | null): CatalogEntry {
 return {id,kind,parent_id:parent,tenant_id:'t',name:id,workspace_id:'space',project_id:'project',description:'',status:'ready',metadata:{},created_at:'2026-10-26'};
}
const rows=[entry('space','workspace',null),entry('project','project','space'),entry('folder','collection','project'),entry('source','source','folder'),entry('policy.pdf','document','source'),entry('records.csv','dataset','source'),entry('internal-chunk','chunk','policy.pdf'),entry('internal-table','table','records.csv')];
describe('Library hierarchy projection',()=>{
 it('shows folders and files without internal source rows',()=>{
  expect(childrenOf(rows,'')).toEqual([rows[0]]);
  expect(childrenOf(rows,'project').map(x=>x.id)).toEqual(['folder']);
  expect(childrenOf(rows,'folder').map(x=>x.id)).toEqual(['policy.pdf','records.csv']);
 });
 it('keeps a source visible while it has no received files',()=>{
  const pending=entry('processing-upload','source','folder');pending.status='processing';
  expect(childrenOf([...rows,pending],'folder').map(x=>x.id)).toEqual(['policy.pdf','processing-upload','records.csv']);
 });
 it('resolves ancestor names and terminates a corrupt cycle',()=>{
  expect(folderTrail(rows,'folder').map(x=>x.name)).toEqual(['space','project','folder']);
  expect(folderTrail([entry('a','collection','b'),entry('b','project','a')],'a')).toHaveLength(2);
 });
 it('offers only supported backend folder kinds',()=>{
  expect(nextFolderKind(undefined)).toBe('workspace');expect(nextFolderKind(rows[0])).toBe('project');
  expect(nextFolderKind(rows[1])).toBe('collection');expect(nextFolderKind(rows[2])).toBe('collection');
  expect(nextFolderKind(entry('nested','corpus','folder'))).toBe('collection');
  expect(nextFolderKind(rows[4])).toBeNull();
 });
});

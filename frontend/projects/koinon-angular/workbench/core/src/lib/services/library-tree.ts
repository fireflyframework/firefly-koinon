// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { CatalogEntry, ResourceKind } from '@fireflyframework/koinon-sdk';
export const FOLDER_KINDS: ResourceKind[] = ['workspace','project','collection','corpus'];
export const isSystemManaged = (entry: CatalogEntry): boolean => entry.system_managed === true;
export const isFolder = (entry: CatalogEntry): boolean => FOLDER_KINDS.includes(entry.kind);
export function childrenOf(entries: CatalogEntry[], parentId: string): CatalogEntry[] {
 const sources=new Set(entries.filter(x=>x.kind==='source'&&x.parent_id===parentId).map(x=>x.id));
 return entries.filter(x=>{
  if(isFolder(x))return (x.parent_id??'')===parentId;
  if(x.kind==='document'||x.kind==='dataset')return sources.has(x.parent_id??'');
  if(x.kind==='source'&&x.parent_id===parentId)return !entries.some(file=>file.parent_id===x.id&&(file.kind==='document'||file.kind==='dataset'));
  return false;
 }).sort((a,b)=>Number(isFolder(b))-Number(isFolder(a))||a.name.localeCompare(b.name));
}
export function folderTrail(entries: CatalogEntry[], parentId: string): CatalogEntry[] {
 const trail:CatalogEntry[]=[],seen=new Set<string>();let id=parentId;
 while(id&&!seen.has(id)){seen.add(id);const entry=entries.find(x=>x.id===id);if(!entry)break;trail.unshift(entry);id=entry.parent_id??'';}
 return trail;
}
export function nextFolderKind(parent:CatalogEntry|undefined):ResourceKind|null{
 return !parent?'workspace':parent.kind==='workspace'?'project':['project','collection','corpus'].includes(parent.kind)?'collection':null;
}
export function friendlyKind(kind:ResourceKind):string{
 return ({workspace:'Space',project:'Project',collection:'Folder',corpus:'Folder',document:'Document',dataset:'Dataset',source:'Source',chunk:'Passage',table:'Table',index_version:'Index',query_session:'Conversation'})[kind];
}
export function resourceIcon(kind:ResourceKind):string{return FOLDER_KINDS.includes(kind)?'folder':kind==='dataset'?'table':kind==='source'?'link':'file';}

export function friendlyStatus(status:string):string{const key=status.toLowerCase();return ({unverified:'Not checked',needs_setup:'Needs setup',disabled:'Disabled',ready:'Ready',active:'Ready',processing:'Processing',running:'Processing',pending:'Pending',queued:'Queued',failed:'Needs attention',error:'Needs attention',cancelled:'Stopped',completed:'Complete',succeeded:'Complete',archived:'Archived'} as Record<string,string>)[key]||status.replaceAll('_',' ').replace(/^./,char=>char.toUpperCase());}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type {Page} from './types.js';
export async function* offsetPages<T>(fetch:(page:number,signal?:AbortSignal)=>Promise<Page<T>>,firstPage=1,signal?:AbortSignal):AsyncGenerator<Page<T>,void,unknown>{
 if(!Number.isSafeInteger(firstPage)||firstPage<1)throw new Error('The first page must be a positive integer');
 let requested=firstPage;
 for(;;){
  signal?.throwIfAborted();
  const page=await fetch(requested,signal);
  signal?.throwIfAborted();
  if(page.page!==undefined&&page.page!==requested)throw new Error('The server returned a different page; traversal stopped');
  yield page;
  if(page.page===undefined||!page.items.length)return;
  const size=page.page_size??page.size;
  const pages=page.pages??(page.total!==undefined&&size!==undefined&&size>0?Math.ceil(page.total/size):undefined);
  if(pages===undefined||requested>=pages)return;
  requested++;
 }
}
export async function* cursorPages<T>(fetch:(after:string|undefined,signal?:AbortSignal)=>Promise<Page<T>>,signal?:AbortSignal):AsyncGenerator<Page<T>,void,unknown>{
 let after:string|undefined;const seen=new Set<string>();
 for(;;){
  signal?.throwIfAborted();const page=await fetch(after,signal);signal?.throwIfAborted();
  const cursor=page.next_cursor;
  if(cursor&&seen.has(cursor))throw new Error('The server repeated a cursor; traversal stopped');
  yield page;
  if(!cursor)return;
  seen.add(cursor);after=cursor;
 }
}

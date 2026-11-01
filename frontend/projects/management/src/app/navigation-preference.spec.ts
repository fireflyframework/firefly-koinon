// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {readNavigationPreference,saveNavigationPreference} from './navigation-preference';
it('retains only a collapsed boolean and ignores unavailable or malformed storage',()=>{
 const values=new Map<string,string>();
 const window={localStorage:{getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>values.set(key,value)}};
 expect(readNavigationPreference(window)).toBe(false);saveNavigationPreference(window,true);expect(readNavigationPreference(window)).toBe(true);saveNavigationPreference(window,false);expect(readNavigationPreference(window)).toBe(false);
 expect([...values.values()]).toEqual(['false']);values.set('koinon-navigation-collapsed','{"tenant":"private"}');expect(readNavigationPreference(window)).toBe(false);
 const denied={get localStorage():Storage{throw new Error('Denied');}};
 expect(readNavigationPreference(denied)).toBe(false);expect(()=>saveNavigationPreference(denied,true)).not.toThrow();expect(readNavigationPreference(null)).toBe(false);
});

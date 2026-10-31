// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {TestBed} from '@angular/core/testing';
import {KoinonButton} from './button';
it('exposes disclosure state on the native button',()=>{
 const fixture=TestBed.createComponent(KoinonButton);fixture.componentRef.setInput('expanded',true);fixture.detectChanges();
 expect(fixture.nativeElement.querySelector('button').getAttribute('aria-expanded')).toBe('true');
 fixture.componentRef.setInput('expanded',false);fixture.detectChanges();
 expect(fixture.nativeElement.querySelector('button').getAttribute('aria-expanded')).toBe('false');
});

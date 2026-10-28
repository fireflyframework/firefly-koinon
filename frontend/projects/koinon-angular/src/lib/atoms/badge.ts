// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {ChangeDetectionStrategy,Component,Input} from '@angular/core';
@Component({selector:'ffk-badge',template:`<span [class]="tone"><ng-content/></span>`,styles:`:host{display:inline-flex}span{font:500 11px/1.4 var(--ffk-font,'Manrope Variable',system-ui,sans-serif);padding:3px 7px;border-radius:5px;color:var(--ui-muted,#62645b);background:var(--ui-subtle,#f3f1eb);border:1px solid var(--ui-line,#d8d4ca)}.attention{color:var(--ui-accent,var(--ffk-gold,#855414));background:color-mix(in srgb,var(--ffk-amber,#ffb34a) 12%,var(--ui-surface,#fff))}.ready{color:var(--ui-text,#272820)}`,changeDetection:ChangeDetectionStrategy.OnPush})
export class KoinonBadge{@Input()tone:'neutral'|'attention'|'ready'='neutral';}

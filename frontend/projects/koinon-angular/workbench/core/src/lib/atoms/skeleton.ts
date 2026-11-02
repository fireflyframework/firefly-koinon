// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {KoinonTextPipe} from '../foundations/i18n';
import {ChangeDetectionStrategy,Component,Input} from '@angular/core';
@Component({imports:[KoinonTextPipe],selector:'ffk-skeleton',host:{'[style.width]':'width'},template:`<span role="status" [attr.aria-label]="label|ffkText" [style.height]="height"></span>`,styles:`:host{display:block;max-width:100%;flex-shrink:0}span{display:block;width:100%;max-width:100%;border-radius:5px;background:var(--ui-line,#d8d4ca);opacity:.45;animation:pulse 1.3s ease-in-out infinite}@keyframes pulse{50%{opacity:.2}}@media(prefers-reduced-motion:reduce){span{animation:none}}`,changeDetection:ChangeDetectionStrategy.OnPush})
export class KoinonSkeleton{@Input()width='100%';@Input()height='16px';@Input()label='Loading';}

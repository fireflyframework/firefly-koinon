// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { KoinonTextPipe } from '../foundations/i18n';
@Component({
  selector: 'ffk-powered-by',
  imports: [KoinonTextPipe],
  template: `{{ 'Powered by' | ffkText
    }}<img
      [src]="
        brandBase + '/logos/koinon-wordmark-' + (theme === 'dark' ? 'reversed' : 'color') + '.svg'
      "
      alt="koinon"
      width="64"
      height="20"
    />`,
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      color: var(--ui-muted);
      font-size: 11px;
      line-height: 20px;
    }
    img {
      display: block;
      object-fit: contain;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonPoweredBy {
  @Input() brandBase = '/assets/brand';
  @Input() theme: 'light' | 'dark' = 'light';
}

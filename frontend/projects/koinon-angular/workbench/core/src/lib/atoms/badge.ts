// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { KoinonIcon } from './icon';
export type StatusTone = 'neutral' | 'attention' | 'ready' | 'error' | 'processing';
export function statusTone(status: string): StatusTone {
  const value = status.toLowerCase();
  if (/^(failed|error|failure)$/.test(value)) return 'error';
  if (/^(ready|active|complete|completed|succeeded|searchable|available|passed)$/.test(value)) return 'ready';
  if (/^(queued|pending|running|processing|indexing|transferring|submitting)$/.test(value)) return 'processing';
  if (/^(unknown|unverified|unavailable|not_checked|awaiting_upload|staging|partial|reconciling|reconciliation_required|cancelled|expired)$/.test(value)) return 'attention';
  return 'neutral';
}
@Component({
  selector: 'ffk-badge',
  imports: [KoinonIcon],
  template: `<span [class]="tone"><ffk-icon [name]="icons[tone]" [style.display]="tone === 'neutral' ? 'none' : null" /><ng-content /></span>`,
  styles: `
    :host { display: inline-flex; max-width: 100%; }
    span { display: inline-flex; align-items: center; gap: 5px; font: 500 11px/1.4 var(--ffk-font,'Manrope Variable',system-ui,sans-serif); padding: 3px 7px; border-radius: 5px; color: var(--ui-muted,#62645b); background: var(--ui-subtle,#f3f1eb); border: 1px solid var(--ui-line,#d8d4ca); }
    .attention { color: light-dark(#855414,#ffcf85); }
    .ready { color: light-dark(#276343,#a9dbba); }
    .error { color: light-dark(#a52d2a,#ffb4ab); }
    .processing { color: light-dark(#245b94,#a8cff7); }
    span:not(.neutral) { background: color-mix(in srgb,currentColor 8%,var(--ui-surface,#fff)); }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonBadge {
  @Input() tone: StatusTone = 'neutral';
  readonly icons = { neutral: 'file', ready: 'check', attention: 'alert', error: 'close', processing: 'clock' };
}

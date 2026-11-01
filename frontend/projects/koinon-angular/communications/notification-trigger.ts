// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
  inject,
} from '@angular/core';
import { KoinonI18n } from '@fireflyframework/koinon-angular';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
registerKoinonSpanish({ Notifications: 'Notificaciones', unread: 'sin leer' });
@Component({
  selector: 'ffk-notification-trigger',
  template: `<button
    type="button"
    [disabled]="disabled"
    [attr.aria-label]="label()"
    [title]="label()"
    (click)="opened.emit()"
  >
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
    </svg>
    @if (count()) {
      <span class="count" aria-hidden="true">{{ count() > 99 ? '99+' : count() }}</span>
    }
  </button>`,
  styles: `
    :host {
      display: inline-flex;
    }
    button {
      position: relative;
      display: grid;
      place-items: center;
      width: 40px;
      height: 40px;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: var(--ui-muted);
      cursor: pointer;
    }
    button:hover:not(:disabled) {
      background: var(--ui-subtle);
      color: var(--ui-text);
    }
    button:focus-visible {
      outline: 2px solid var(--ui-accent);
      outline-offset: 2px;
    }
    button:disabled {
      cursor: not-allowed;
    }
    svg {
      width: 18px;
      height: 18px;
    }
    .count {
      position: absolute;
      top: 0;
      right: -2px;
      display: grid;
      place-items: center;
      min-width: 17px;
      height: 17px;
      padding: 0 4px;
      border-radius: 9px;
      background: var(--ui-action);
      color: var(--ui-action-text);
      font: 600 9px/1 var(--ffk-font, 'Manrope', sans-serif);
      font-variant-numeric: tabular-nums;
    }
    @media (max-width: 700px), (pointer: coarse) {
      button {
        width: 44px;
        height: 44px;
      }
      .count {
        top: 1px;
        right: 0;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonNotificationTrigger {
  @Input() unread: number | null = null;
  @Input() disabled = false;
  @Output() opened = new EventEmitter<void>();
  private readonly i18n = inject(KoinonI18n);
  count() {
    return typeof this.unread === 'number' && Number.isFinite(this.unread)
      ? Math.max(0, Math.floor(this.unread))
      : 0;
  }
  label() {
    const count = this.count();
    return (
      this.i18n.text('Notifications') + (count ? ', ' + count + ' ' + this.i18n.text('unread') : '')
    );
  }
}

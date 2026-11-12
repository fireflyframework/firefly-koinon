// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  Input,
  OnInit,
  effect,
  inject,
  signal,
} from '@angular/core';
import { KoinonButton } from '@fireflyframework/koinon-angular/workbench/core';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench/bootstrap';
import type { SessionMonitor } from './session-monitor';
import { SessionService } from './session.service';

const spanish: Readonly<Record<string, string>> = {
  Session: 'Sesión',
  'Your session ends soon.': 'Tu sesión caducará pronto.',
  'Checking your session.': 'Comprobando tu sesión.',
  'Your session has ended.': 'Tu sesión ha caducado.',
  'Renew session': 'Renovar sesión',
  'Waiting for sign-in': 'Esperando el inicio de sesión',
  'Complete sign-in in the new window, then return here.':
    'Completa el inicio de sesión en la nueva ventana y vuelve aquí.',
  'View session details': 'Ver detalles de sesión',
  'Renewal could not be confirmed. No requests were retried.':
    'No se ha podido confirmar la renovación. No se ha repetido ninguna solicitud.',
  'Your account changed. The previous draft was cleared.':
    'Has cambiado de cuenta. Se ha eliminado el borrador anterior.',
  'Session renewed. Review your Library draft and any earlier request before saving.':
    'Sesión renovada. Revisa el borrador de Biblioteca y cualquier solicitud anterior antes de guardar.',
  'Session renewed. No requests were retried.':
    'Sesión renovada. No se ha repetido ninguna solicitud.',
  'Current access changed. Your draft was not restored.':
    'Tus permisos han cambiado. No se ha restaurado el borrador.',
  'Dismiss session message': 'Cerrar mensaje de sesión',
};

@Component({
  selector: 'app-session-notice',
  imports: [KoinonButton],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `@if (monitor(); as m) {
    @if (visible(m)) {
      @if (surface === 'account') {
        <button
          class="session-trigger"
          type="button"
          [attr.aria-expanded]="expanded()"
          aria-controls="session-details"
          [attr.aria-label]="status(m) + ' ' + text('View session details')"
          (click)="expanded.set(!expanded())"
        >
          <span class="indicator" aria-hidden="true"></span>{{ text('Session') }}
        </button>
        <span class="sr-only" role="status">{{ status(m) }}</span>
      }
      @if (surface !== 'account' || expanded()) {
        <aside
          [id]="surface === 'account' ? 'session-details' : null"
          class="notice"
          [class.compact]="surface === 'dialog'"
          [class.details]="surface === 'account'"
          [attr.aria-label]="text('Session')"
          role="region"
        >
          <div class="copy">
            <p [attr.role]="surface === 'account' ? null : 'status'">{{ status(m) }}</p>
            @if (m.message() && (m.renewing() || warning(m) || workbench.f.authRequired())) {
              <p>{{ text(m.message()) }}</p>
            }
            @if (
              surface !== 'dialog' &&
              !workbench.f.authRequired() &&
              m.remaining() !== null &&
              m.remaining()! > 0
            ) {
              <span role="timer" aria-live="off">{{ time(m.remaining()!) }}</span>
            }
          </div>
          @if (
            surface !== 'auth' &&
            m.canRenew() &&
            (warning(m) || workbench.f.authRequired() || m.renewing())
          ) {
            <ffk-button
              type="button"
              variant="quiet"
              [loading]="m.renewing()"
              (click)="m.renew()"
              >{{ text(m.renewing() ? 'Waiting for sign-in' : 'Renew session') }}</ffk-button
            >
          }
          @if (surface !== 'auth' && m.message() && !warning(m) && !m.renewing()) {
            <ffk-button
              type="button"
              variant="quiet"
              icon="close"
              [label]="text('Dismiss session message')"
              (click)="m.message.set('')"
            />
          }
        </aside>
      }
    }
  }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
      position: relative;
    }
    .notice {
      display: flex;
      align-items: center;
      gap: 16px;
      margin: 12px 20px;
      padding: 12px 16px;
      border: 1px solid var(--ui-line, #d8d4ca);
      border-radius: 8px;
      background: var(--ui-canvas, #f3f1eb);
      color: var(--ui-text, #272820);
      font: 400 13px/1.5 var(--ffk-font, 'Manrope Variable', Manrope, sans-serif);
    }
    .notice.compact {
      margin: 12px 0 0;
      padding: 0;
      border: 0;
      background: transparent;
      border-radius: 0;
      gap: 8px;
      flex-wrap: wrap;
      font-size: 14px;
    }
    .notice.details {
      position: absolute;
      z-index: 20;
      inset-inline-end: 0;
      top: calc(100% + 8px);
      width: min(360px, calc(100vw - 32px));
      max-height: min(440px, 70vh);
      overflow: auto;
      box-sizing: border-box;
      margin: 0;
      padding: 16px;
      flex-wrap: wrap;
      border-radius: 12px;
      font-size: 14px;
    }
    .session-trigger {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 44px;
      padding: 6px 8px;
      border: 0;
      border-radius: 8px;
      background: transparent;
      color: var(--ui-text, #272820);
      font: 600 13px/1.4 var(--ffk-font, 'Manrope Variable', Manrope, sans-serif);
      cursor: pointer;
    }
    .session-trigger:hover {
      background: var(--ui-canvas, #f3f1eb);
    }
    .session-trigger:focus-visible {
      outline: 2px solid var(--ui-focus, #4b5b39);
      outline-offset: 2px;
    }
    .indicator {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: currentColor;
    }
    .sr-only {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      overflow: hidden;
      clip-path: inset(50%);
      white-space: nowrap;
    }
    .copy {
      flex: 1;
      min-width: 0;
    }
    .copy p {
      margin: 0;
    }
    .copy p + p {
      margin-top: 4px;
    }
    [role='timer'] {
      display: inline-block;
      margin-inline-start: 8px;
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      white-space: nowrap;
    }
    @media (max-width: 600px) {
      .notice {
        margin: 8px;
        gap: 8px;
        flex-wrap: wrap;
        padding: 12px;
      }
      .notice.details {
        position: fixed;
        inset-inline: 16px;
        top: 64px;
        width: auto;
      }
      .notice:not(.compact) .copy {
        flex-basis: 100%;
      }
      .notice.compact .copy {
        flex: 1 1 170px;
      }
    }
  `,
})
export class SessionNotice implements OnInit {
  @Input({ required: true }) workbench!: KoinonWorkbench;
  @Input() surface: 'content' | 'account' | 'dialog' | 'auth' = 'content';
  private readonly sessions = inject(SessionService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly expanded = signal(false);
  @HostListener('document:click', ['$event']) outside(event: Event) {
    if (!event.composedPath().includes(this.host.nativeElement)) this.expanded.set(false);
  }
  @HostListener('keydown.escape', ['$event']) close(event: Event) {
    if (!this.expanded()) return;
    event.stopPropagation();
    this.expanded.set(false);
    this.host.nativeElement.querySelector<HTMLButtonElement>('.session-trigger')?.focus();
  }
  status(monitor: SessionMonitor) {
    return this.text(
      monitor.renewing()
        ? 'Waiting for sign-in'
        : this.workbench.f.authRequired()
          ? 'Your session has ended.'
          : this.warning(monitor)
            ? monitor.remaining() === 0
              ? 'Checking your session.'
              : 'Your session ends soon.'
            : monitor.message(),
    );
  }
  readonly monitor = signal<SessionMonitor | null>(null);
  constructor() {
    effect(() => {
      const monitor = this.monitor();
      if (monitor) {
        this.workbench.dialog();
        this.workbench.f.authRequired();
        this.workbench.f.context();
        monitor.draft.track();
        if (!this.visible(monitor)) {
          const root = this.host.nativeElement.getRootNode() as Document | ShadowRoot;
          if (this.host.nativeElement.contains(root.activeElement)) {
            const dialog = this.host.nativeElement.closest('[role="dialog"]');
            const next = dialog
              ? dialog.querySelector<HTMLButtonElement>('.dialog-actions button:not([disabled])')
              : this.host.nativeElement
                  .closest('ffk-shell')
                  ?.querySelector<HTMLButtonElement>('.account-avatar');
            next?.focus();
          }
          this.expanded.set(false);
        }
      }
    });
  }
  async ngOnInit() {
    this.monitor.set(await this.sessions.monitor(this.workbench));
  }
  warning(monitor: SessionMonitor) {
    const remaining = monitor.remaining();
    return remaining !== null && remaining <= 120;
  }
  visible(monitor: SessionMonitor) {
    return (
      this.warning(monitor) ||
      monitor.renewing() ||
      !!monitor.message() ||
      (this.workbench.f.authRequired() && monitor.canRenew())
    );
  }
  text(value: string) {
    return this.workbench.i18n.preferences().locale.toLowerCase().startsWith('es')
      ? (spanish[value] ?? value)
      : value;
  }
  time(seconds: number) {
    return Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
  }
}

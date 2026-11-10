// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { Component, Input, OnInit, effect, inject, signal } from '@angular/core';
import { KoinonButton, type KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import type { SessionMonitor } from './session-monitor';
import { SessionService } from './session.service';

const spanish: Readonly<Record<string, string>> = {
  Session: 'Sesión',
  'Your session ends soon.': 'Tu sesión caducará pronto.',
  'Checking your session.': 'Comprobando tu sesión.',
  'Your session has ended.': 'Tu sesión ha caducado.',
  'Renew session': 'Renovar sesión',
  'Waiting for sign-in': 'Esperando el inicio de sesión',
  'Complete sign-in in the new window. This page will keep your work.':
    'Completa el inicio de sesión en la nueva ventana. Esta página conservará tu trabajo.',
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
  template: `@if (monitor(); as m) {
    @if (visible(m)) {
      <aside class="notice" [attr.aria-label]="text('Session')">
        <div class="copy">
          @if (warning(m) || workbench.f.authRequired()) {
            <p role="status">
              {{
                text(
                  workbench.f.authRequired()
                    ? 'Your session has ended.'
                    : m.remaining() === 0
                      ? 'Checking your session.'
                      : 'Your session ends soon.'
                )
              }}
              @if (!workbench.f.authRequired() && m.remaining() !== null && m.remaining()! > 0) {
                <span role="timer" aria-live="off">{{ time(m.remaining()!) }}</span>
              }
            </p>
          }
          @if (m.message()) {
            <p role="status">{{ text(m.message()) }}</p>
          }
        </div>
        @if (m.canRenew() && (warning(m) || workbench.f.authRequired() || m.renewing())) {
          <ffk-button variant="quiet" [loading]="m.renewing()" (click)="m.renew()">{{
            text(m.renewing() ? 'Waiting for sign-in' : 'Renew session')
          }}</ffk-button>
        }
        @if (m.message() && !warning(m) && !m.renewing()) {
          <ffk-button
            variant="quiet"
            icon="close"
            [label]="text('Dismiss session message')"
            (click)="m.message.set('')"
          />
        }
      </aside>
    }
  }`,
  styles: `
    :host {
      display: block;
      min-width: 0;
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
      .copy {
        flex-basis: 100%;
      }
    }
  `,
})
export class SessionNotice implements OnInit {
  @Input({ required: true }) workbench!: KoinonWorkbench;
  private readonly sessions = inject(SessionService);
  readonly monitor = signal<SessionMonitor | null>(null);
  constructor() {
    effect(() => {
      const monitor = this.monitor();
      if (monitor) {
        this.workbench.dialog();
        this.workbench.f.authRequired();
        this.workbench.f.context();
        monitor.draft.track();
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

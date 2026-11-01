// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import { firstValueFrom } from 'rxjs';
import { SessionClock, sessionInstant, type BrowserSession } from './session-clock';
import { LibrarySessionDraft } from './session-recovery';
import type { SessionService } from './session.service';

export class SessionMonitor {
  readonly remaining = signal<number | null>(null);
  readonly renewing = signal(false);
  readonly message = signal('');
  readonly draft: LibrarySessionDraft;
  private readonly clock = new SessionClock();
  private current: BrowserSession | null = null;
  private attempt: { subject: string; authenticated: string | null; until: number } | null = null;
  private reading = false;
  private stopped = false;
  private ticks = 0;
  private readonly timer: ReturnType<typeof setInterval>;
  private readonly visible = () => {
    if (!document.hidden) void this.read();
  };
  constructor(
    private readonly http: HttpClient,
    readonly workbench: KoinonWorkbench,
    private readonly sessions: SessionService,
  ) {
    this.draft = new LibrarySessionDraft(workbench);
    sessions.renewalHandler = () => {
      if (!this.canRenew()) return false;
      void this.renew();
      return true;
    };
    this.timer = setInterval(() => {
      if (this.stopped) return;
      const left = this.clock.remaining(performance.now());
      this.remaining.set(left);
      if (this.attempt && performance.now() >= this.attempt.until && this.renewing()) {
        this.renewing.set(false);
        this.message.set('Renewal could not be confirmed. No requests were retried.');
      }
      if (++this.ticks % (this.renewing() ? 2 : 30) === 0 || left === 0) void this.read();
    }, 1000);
    document.addEventListener('visibilitychange', this.visible);
    void this.read();
  }
  canRenew(): boolean {
    return (
      Number.isFinite(sessionInstant(this.current?.expires_at)) &&
      !!this.workbench.f.context()?.subject
    );
  }
  async renew(): Promise<void> {
    if (this.stopped || this.renewing() || !this.canRenew()) return;
    const subject = this.workbench.f.context()!.subject;
    if (subject !== this.current?.subject) return;
    this.draft.track();
    this.draft.capture();
    this.attempt = {
      subject,
      authenticated: this.current.authenticated_at ?? null,
      until: performance.now() + 120000,
    };
    this.renewing.set(true);
    this.message.set('Complete sign-in in the new window. This page will keep your work.');
    // No opener relationship, return URL, token or request body is handed to the sign-in window.
    window.open(
      '/oauth2/authorization/koinon',
      '_blank',
      'noopener,noreferrer,popup,width=520,height=760',
    );
  }
  async read(): Promise<void> {
    if (this.reading || this.stopped) return;
    this.reading = true;
    const started = performance.now();
    try {
      const value = await firstValueFrom(
        this.http.get<BrowserSession>('/auth/me', { withCredentials: true, timeout: 5000 }),
      );
      if (this.stopped) return;
      if (value.authenticated !== true || !value.subject) {
        this.clock.clear();
        return;
      }
      const previous = this.current;
      this.current = value;
      this.clock.observe(value, started, performance.now());
      this.remaining.set(this.clock.remaining(performance.now()));
      if (previous?.subject && previous.subject !== value.subject) {
        this.draft.clear();
        this.attempt = null;
        this.renewing.set(false);
        await this.workbench.f.revalidateSession(previous.subject);
        this.message.set('Your account changed. The previous draft was cleared.');
      } else if (
        this.attempt &&
        value.subject === this.attempt.subject &&
        value.authenticated_at &&
        value.authenticated_at !== this.attempt.authenticated &&
        Number.isFinite(sessionInstant(value.authenticated_at)) &&
        (this.remaining() ?? 0) > 0
      ) {
        const wasExpired = this.workbench.f.authRequired();
        const expected = this.attempt.subject;
        this.attempt = null;
        this.renewing.set(false);
        if (await this.workbench.f.revalidateSession(expected)) {
          const restored = wasExpired && (await this.draft.restore());
          this.message.set(
            restored
              ? 'Session renewed. Review your Library draft and any earlier request before saving.'
              : 'Session renewed. No requests were retried.',
          );
        } else {
          this.draft.clear();
          this.message.set('Current access changed. Your draft was not restored.');
        }
      }
    } catch (error) {
      if (this.stopped) return;
      this.clock.clear();
      this.remaining.set(null);
      if (error instanceof HttpErrorResponse && error.status === 401) {
        this.draft.track();
        this.draft.capture();
        if (this.workbench.f.context()) this.workbench.f.authRequired.set(true);
      }
    } finally {
      this.reading = false;
    }
  }
  stop(): void {
    this.stopped = true;
    clearInterval(this.timer);
    document.removeEventListener('visibilitychange', this.visible);
    this.attempt = this.current = null;
    this.draft.clear();
    this.clock.clear();
    this.remaining.set(null);
    this.message.set('');
    this.sessions.renewalHandler = undefined;
  }
}

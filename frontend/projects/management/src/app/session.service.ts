// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { AccountNavigation } from './account-navigation';
import type { KoinonWorkbench } from '@fireflyframework/koinon-angular/workbench';
import type { SessionMonitor } from './session-monitor';
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly http = inject(HttpClient);
  private readonly navigation = inject(AccountNavigation);
  readonly error = signal('');
  renewalHandler?: () => boolean;
  private runtime?: Promise<SessionMonitor>;
  monitor(workbench: KoinonWorkbench): Promise<SessionMonitor> {
    return (this.runtime ??= import('./session-monitor').then(
      ({ SessionMonitor }) => new SessionMonitor(this.http, workbench, this),
    ));
  }
  signIn(): void {
    if (this.renewalHandler?.()) return;
    this.navigation.retainForSignIn();
    window.location.assign('/oauth2/authorization/koinon');
  }
  async signOut(): Promise<boolean> {
    this.error.set('');
    try {
      const { signOut } = await import('./session-sign-out');
      const error = await signOut(this.http);
      if (error) {
        this.error.set(error);
        return false;
      }
      void this.runtime?.then((monitor) => monitor.stop());
      this.navigation.clearPending();
      return true;
    } catch {
      this.error.set('Sign-out could not be confirmed. Reload this page or try again.');
      return false;
    }
  }
}

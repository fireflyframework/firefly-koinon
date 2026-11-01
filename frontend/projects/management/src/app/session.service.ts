// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { AccountNavigation } from './account-navigation';
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly http = inject(HttpClient);
  private readonly navigation = inject(AccountNavigation);
  readonly error = signal('');
  signIn(): void {
    this.navigation.retainForSignIn();
    window.location.assign('/oauth2/authorization/koinon');
  }
  async signOut(): Promise<boolean> {
    this.error.set('');
    try {
      await firstValueFrom(
        this.http.post(
          '/logout',
          {},
          { withCredentials: true, responseType: 'text', timeout: 10000 },
        ),
      );
    } catch {
      // Native logout may clear the cookie before a followed redirect fails.
    }
    try {
      const current = await firstValueFrom(
        this.http.get<{ authenticated?: boolean }>('/auth/me', {
          withCredentials: true,
          timeout: 5000,
        }),
      );
      this.error.set(
        current.authenticated === true
          ? 'You are still signed in. Try signing out again.'
          : 'Sign-out could not be confirmed. Reload this page or try again.',
      );
    } catch (error) {
      if (error instanceof HttpErrorResponse && error.status === 401) {
        this.navigation.clearPending();
        return true;
      }
      this.error.set('Sign-out could not be confirmed. Reload this page or try again.');
    }
    return false;
  }
}

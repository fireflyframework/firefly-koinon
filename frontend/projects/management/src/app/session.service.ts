// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { HttpClient } from '@angular/common/http';
import { inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly http = inject(HttpClient);
  readonly error = signal('');
  signIn(): void {
    window.location.assign('/oauth2/authorization/koinon');
  }
  async signOut(): Promise<boolean> {
    this.error.set('');
    try {
      await firstValueFrom(this.http.post('/logout', {}, { withCredentials: true }));
      return true;
    } catch {
      this.error.set('Sign out did not complete. Your session has not been cleared.');
      return false;
    }
  }
}

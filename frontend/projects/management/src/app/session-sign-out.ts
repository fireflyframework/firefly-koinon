// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export async function signOut(http: HttpClient): Promise<string | null> {
  try {
    await firstValueFrom(
      http.post('/logout', {}, { withCredentials: true, responseType: 'text', timeout: 10000 }),
    );
  } catch {
    // Native logout may clear the cookie before a followed redirect fails.
  }
  try {
    const current = await firstValueFrom(
      http.get<{ authenticated?: boolean }>('/auth/me', { withCredentials: true, timeout: 5000 }),
    );
    return current.authenticated === true
      ? 'You are still signed in. Try signing out again.'
      : 'Sign-out could not be confirmed. Reload this page or try again.';
  } catch (error) {
    return error instanceof HttpErrorResponse && error.status === 401
      ? null
      : 'Sign-out could not be confirmed. Reload this page or try again.';
  }
}

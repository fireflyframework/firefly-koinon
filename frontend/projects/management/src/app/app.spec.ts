// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { provideHttpClient, withXsrfConfiguration } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SessionService } from './session.service';
import { AccountNavigation } from './account-navigation';
describe('browser session boundary', () => {
  beforeEach(() =>
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(
          withXsrfConfiguration({ cookieName: 'XSRF-TOKEN', headerName: 'X-XSRF-TOKEN' }),
        ),
        provideHttpClientTesting(),
      ],
    }),
  );
  afterEach(() => TestBed.inject(HttpTestingController).verify());
  it('posts logout to the native endpoint and waits for server confirmation', async () => {
    const service = TestBed.inject(SessionService);
    const cleared = vi.spyOn(TestBed.inject(AccountNavigation), 'clearPending');
    const result = service.signOut();
    const request = TestBed.inject(HttpTestingController).expectOne('/logout');
    expect(request.request.method).toBe('POST');
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.responseType).toBe('text');
    request.flush(null, { status: 204, statusText: 'No Content' });
    (await vi.waitFor(() => TestBed.inject(HttpTestingController).expectOne('/auth/me'))).flush(
      {},
      { status: 401, statusText: 'Unauthorized' },
    );
    expect(await result).toBe(true);
    expect(service.error()).toBe('');
    expect(cleared).toHaveBeenCalledOnce();
  });
  it('keeps a failed logout visible instead of claiming the session is gone', async () => {
    const service = TestBed.inject(SessionService);
    const cleared = vi.spyOn(TestBed.inject(AccountNavigation), 'clearPending');
    const result = service.signOut();
    const request = TestBed.inject(HttpTestingController).expectOne('/logout');
    request.flush({ detail: 'Unavailable' }, { status: 503, statusText: 'Service unavailable' });
    (await vi.waitFor(() => TestBed.inject(HttpTestingController).expectOne('/auth/me'))).flush({
      authenticated: true,
    });
    expect(await result).toBe(false);
    expect(cleared).not.toHaveBeenCalled();
    expect(service.error()).toContain('still signed in');
  });
  it('recognizes a cleared session even when the native logout redirect target fails', async () => {
    const service = TestBed.inject(SessionService);
    const result = service.signOut();
    TestBed.inject(HttpTestingController)
      .expectOne('/logout')
      .flush('Not found', { status: 404, statusText: 'Not found' });
    (await vi.waitFor(() => TestBed.inject(HttpTestingController).expectOne('/auth/me'))).flush(
      {},
      { status: 401, statusText: 'Unauthorized' },
    );
    expect(await result).toBe(true);
    expect(service.error()).toBe('');
  });
  it('accepts a native HTML redirect response only after checking the authenticated session', async () => {
    const service = TestBed.inject(SessionService);
    const result = service.signOut();
    TestBed.inject(HttpTestingController)
      .expectOne('/logout')
      .flush('<!doctype html><title>Signed out</title>');
    (await vi.waitFor(() => TestBed.inject(HttpTestingController).expectOne('/auth/me'))).flush(
      {},
      { status: 401, statusText: 'Unauthorized' },
    );
    expect(await result).toBe(true);
  });
  it('reports unknown verification honestly without claiming that the cookie was retained', async () => {
    const service = TestBed.inject(SessionService);
    const result = service.signOut();
    TestBed.inject(HttpTestingController)
      .expectOne('/logout')
      .flush(null, { status: 204, statusText: 'No content' });
    (await vi.waitFor(() => TestBed.inject(HttpTestingController).expectOne('/auth/me'))).flush(
      {},
      { status: 503, statusText: 'Unavailable' },
    );
    expect(await result).toBe(false);
    expect(service.error()).toContain('could not be confirmed');
    expect(service.error()).not.toContain('has not been cleared');
  });
});

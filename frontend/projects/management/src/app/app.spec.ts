// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { provideHttpClient, withXsrfConfiguration } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SessionService } from './session.service';
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
    const result = service.signOut();
    const request = TestBed.inject(HttpTestingController).expectOne('/logout');
    expect(request.request.method).toBe('POST');
    expect(request.request.withCredentials).toBe(true);
    request.flush(null, { status: 204, statusText: 'No Content' });
    expect(await result).toBe(true);
    expect(service.error()).toBe('');
  });
  it('keeps a failed logout visible instead of claiming the session is gone', async () => {
    const service = TestBed.inject(SessionService);
    const result = service.signOut();
    const request = TestBed.inject(HttpTestingController).expectOne('/logout');
    request.flush({ detail: 'Unavailable' }, { status: 503, statusText: 'Service unavailable' });
    expect(await result).toBe(false);
    expect(service.error()).toContain('has not been cleared');
  });
});

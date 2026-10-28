// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, KoinonI18n, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonAuditService } from '../../../settings/src/audit-service';
function setup(request: KoinonTransport['request']) {
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw new Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    providers: [
      KoinonFacade,
      KoinonAuditService,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('north');
  const i18n = TestBed.inject(KoinonI18n);
  i18n.apply({ locale: 'es-MX', time_zone: 'America/Mexico_City', response_language: 'es' });
  return { service: TestBed.inject(KoinonAuditService), facade };
}
describe('Organization audit requests', () => {
  it('sends real server pages, names, action, subject and date filters with the chosen time zone', async () => {
    const calls: RequestOptions[] = [];
    const { service } = setup(
      async <T>(_method: unknown, path: string, options?: RequestOptions) => {
        expect(path).toBe('/tenants/north/audit');
        calls.push(options ?? {});
        return { items: [], actors: {}, total: 63, page: 3, page_size: 10, pages: 7 } as T;
      },
    );
    await service.load({
      q: 'Research',
      action: 'membership.created',
      subject: 'issuer|person',
      from_date: '2026-10-01',
      through_date: '2026-10-27',
      page: 3,
      page_size: 10,
      sort: 'created_at',
      order: 'desc',
    });
    expect(calls[0].query).toEqual({
      q: 'Research',
      action: 'membership.created',
      subject: 'issuer|person',
      from_date: '2026-10-01',
      through_date: '2026-10-27',
      page: 3,
      page_size: 10,
      sort: 'created_at',
      order: 'desc',
      time_zone: 'America/Mexico_City',
    });
    expect(service.page()?.total).toBe(63);
    expect(service.page()?.items.length).toBe(0);
  });
  it('keeps403 as a visible error and propagates401 to session expiry', async () => {
    let status = 403;
    const { service, facade } = setup(async () => {
      throw new KoinonError(status, 'DENIED', 'Denied');
    });
    await service.load();
    expect(service.error()?.message).toBe('Denied');
    expect(facade.authRequired()).toBe(false);
    status = 401;
    await service.load();
    expect(facade.authRequired()).toBe(true);
  });
  it('discards an old organization response after a newer request', async () => {
    let complete: ((value: unknown) => void) | undefined;
    let call = 0;
    const { service, facade } = setup(<T>() => {
      ++call;
      if (call === 1)
        return new Promise<T>((resolve) => {
          complete = resolve as (value: unknown) => void;
        });
      return Promise.resolve({
        items: [],
        actors: {},
        total: 1,
        page: 1,
        page_size: 25,
        pages: 1,
      } as T);
    });
    const first = service.load();
    facade.tenantId.set('south');
    await service.load();
    complete?.({ items: [], actors: {}, total: 99, page: 1, page_size: 25, pages: 4 });
    await first;
    expect(service.page()?.total).toBe(1);
  });
});

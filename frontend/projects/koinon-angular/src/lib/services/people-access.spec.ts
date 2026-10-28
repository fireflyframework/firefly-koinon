// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonPeopleService } from '../../../settings/src/people-service';
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
      KoinonPeopleService,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  const facade = TestBed.inject(KoinonFacade);
  facade.tenantId.set('north');
  return { service: TestBed.inject(KoinonPeopleService), facade };
}
describe('People and access requests', () => {
  it('sends server page, name, role and workspace filters without slicing results', async () => {
    const calls: RequestOptions[] = [];
    const { service } = setup(
      async <T>(_method: unknown, _path: string, options?: RequestOptions) => {
        calls.push(options ?? {});
        return { items: [], actors: {}, total: 73, page: 2, page_size: 25, pages: 3 } as T;
      },
    );
    await service.load({
      q: 'Research',
      role: 'editor',
      workspace_id: 'space',
      scope: 'workspace',
      page: 2,
      page_size: 25,
    });
    expect(calls[0].query).toEqual({
      q: 'Research',
      role: 'editor',
      workspace_id: 'space',
      scope: 'workspace',
      page: 2,
      page_size: 25,
    });
    expect(service.members()?.total).toBe(73);
    expect(service.members()?.page).toBe(2);
  });
  it('uses directory cursor and clears a one-time secret after dismissal', async () => {
    const calls: [string, RequestOptions | undefined][] = [];
    const { service } = setup(
      async <T>(_method: unknown, path: string, options?: RequestOptions) => {
        calls.push([path, options]);
        return (
          path.endsWith('people')
            ? { items: [], next_cursor: 'next' }
            : { invitation: { id: 'invite' }, token: 'one-time-private-token' }
        ) as T;
      },
    );
    await service.searchPeople('Ana', 'cursor');
    expect(calls[0][1]?.query).toEqual({ q: 'Ana', limit: 20, after: 'cursor' });
    await service.invite({ role: 'viewer' });
    expect(service.created()?.token).toBe('one-time-private-token');
    service.clearSecret();
    expect(service.created()).toBeNull();
  });
  it('propagates expired auth but keeps denied actions as an error', async () => {
    let status = 401;
    const { service, facade } = setup(async () => {
      throw new KoinonError(status, 'ACCESS_DENIED', 'Denied');
    });
    await service.load();
    expect(facade.authRequired()).toBe(true);
    facade.authRequired.set(false);
    status = 403;
    await service.load();
    expect(facade.authRequired()).toBe(false);
    expect(service.error()).not.toBeNull();
  });
});

it('does not publish a directory result after the tenant changed', async () => {
  let complete: (value: unknown) => void = () => undefined;
  const { service, facade } = setup(
    <T>() =>
      new Promise<T>((resolve) => {
        complete = resolve as (value: unknown) => void;
      }),
  );
  const request = service.searchPeople('Ana');
  facade.tenantId.set('south');
  complete({ items: [{ subject: 'private', display_name: 'Ana' }] });
  await request;
  expect(service.directory()).toBeNull();
});

it('keeps directory and avatar access within a workspace administrator’s scope', async () => {
  const queries: RequestOptions[] = [];
  const { service, facade } = setup(
    async <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      queries.push(options ?? {});
      return { items: [], next_cursor: null } as T;
    },
  );
  facade.context.set({
    subject: 'issuer|admin',
    tenants: [],
    workspaces: [],
    memberships: [
      {
        id: 'grant',
        subject: 'issuer|admin',
        tenant_id: 'north',
        workspace_id: 'space',
        role: 'admin',
        active: true,
      },
    ],
  });
  facade.workspaceId.set('space');
  await service.searchPeople('Ana');
  expect(queries[0].query?.['workspace_id']).toBe('space');
});

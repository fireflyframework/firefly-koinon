// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonFacade,
  KoinonClientContext,
  KOINON_TRANSPORT,
} from '@fireflyframework/koinon-angular';
import { KoinonCommunicationsSession } from '../../../../communications/runtime/session';
it('discards responses and errors after subject or tenant changes', async () => {
  const subject = signal('alice'),
    tenant = signal('org'),
    revision = signal(0);
  TestBed.configureTestingModule({
    providers: [
      KoinonCommunicationsSession,
      {
        provide: KoinonFacade,
        useValue: {
          context: () => ({ subject: subject() }),
          tenantId: tenant,
          authRequired: signal(false),
        },
      },
      {
        provide: KoinonClientContext,
        useValue: { revision, getTransport: () => ({ request: async () => ({}) }) },
      },
      { provide: KOINON_TRANSPORT, useValue: { request: async () => ({}) } },
    ],
  });
  const session = TestBed.inject(KoinonCommunicationsSession);
  let complete: (value: string) => void = () => {
    /* resolved by the controlled request */
  };
  const applied: string[] = [];
  const request = session.run(
    'load',
    () => new Promise<string>((resolve) => (complete = resolve)),
    (value) => applied.push(value),
  );
  subject.set('bob');
  complete('alice-private-notice');
  await request;
  expect(applied).toEqual([]);
  let reject: (reason: Error) => void = () => {
    /* resolved by the controlled request */
  };
  const failure = session.run(
    'load',
    () => new Promise<string>((_, fail) => (reject = fail)),
    (value) => applied.push(value),
  );
  tenant.set('other');
  reject(new Error('private details'));
  await failure;
  expect(session.error()).toBe('');
});
it('only applies the newest response on the same request channel', async () => {
  TestBed.configureTestingModule({
    providers: [
      KoinonCommunicationsSession,
      {
        provide: KoinonFacade,
        useValue: {
          context: () => ({ subject: 'alice' }),
          tenantId: () => 'org',
          authRequired: signal(false),
        },
      },
      {
        provide: KoinonClientContext,
        useValue: { revision: signal(0), getTransport: () => ({ request: async () => ({}) }) },
      },
      { provide: KOINON_TRANSPORT, useValue: { request: async () => ({}) } },
    ],
  });
  const session = TestBed.inject(KoinonCommunicationsSession);
  let first: (value: string) => void = () => {
    /* resolved by the controlled request */
  };
  const result: string[] = [];
  const slow = session.run(
    'search',
    () => new Promise<string>((resolve) => (first = resolve)),
    (v) => result.push(v),
  );
  await session.run(
    'search',
    async () => 'new',
    (v) => result.push(v),
  );
  first('old');
  await slow;
  expect(result).toEqual(['new']);
});

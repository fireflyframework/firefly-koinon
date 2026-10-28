// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  KoinonError,
  type KoinonTransport,
  type HttpMethod,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade, provideKoinonClient } from '@fireflyframework/koinon-angular';
import { KoinonConfiguration } from '../../../../settings/src/configuration';
const provider = {
  id: 'p',
  name: 'Local model',
  kind: 'ollama',
  base_url: 'http://127.0.0.1:11434',
  model_ids: ['local-model'],
  enabled: true,
  revision: 1,
  secret_configured: false,
  validated: false,
  checks: [],
};
describe('observed configuration checks', () => {
  it('keeps a saved provider unvalidated when the real check fails', async () => {
    const transport: KoinonTransport = {
      request: async <T>(method: HttpMethod, path: string) => {
        if (path.endsWith('/validate'))
          throw new KoinonError(503, 'MODEL_UNAVAILABLE', 'The model server is unavailable');
        return (
          path.endsWith('/configuration')
            ? { providers: [], provider_types: [], connections: [], checks: [] }
            : path.endsWith('/agents')
              ? { items: [] }
              : method === 'POST'
                ? provider
                : {}
        ) as T;
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
    TestBed.configureTestingModule({
      providers: [
        KoinonFacade,
        KoinonConfiguration,
        ...provideKoinonClient(new KoinonClient({ transport }), transport),
      ],
    });
    TestBed.inject(KoinonFacade).tenantId.set('tenant');
    const service = TestBed.inject(KoinonConfiguration);
    await service.load();
    expect(
      await service.saveProvider(null, {
        name: 'Local model',
        kind: 'ollama',
        base_url: provider.base_url,
        model_ids: provider.model_ids,
      }),
    ).toMatchObject({ validated: false });
    expect(await service.validateProvider('p')).toBeNull();
    expect(service.configuration()?.providers[0].validated).toBe(false);
    expect(service.error()).toBe('The model server is unavailable');
  });
});
for (const status of [401, 403])
  it(`configuration ${status} preserves the session-expiry boundary`, async () => {
    const transport: KoinonTransport = {
      request: async () => {
        throw new KoinonError(status, 'DENIED', 'Observed request failure');
      },
      stream: () => {
        throw new Error('Unexpected stream');
      },
    };
    TestBed.configureTestingModule({
      providers: [
        KoinonFacade,
        KoinonConfiguration,
        ...provideKoinonClient(new KoinonClient({ transport }), transport),
      ],
    });
    const f = TestBed.inject(KoinonFacade);
    f.tenantId.set('tenant');
    const configuration = TestBed.inject(KoinonConfiguration);
    await configuration.load();
    expect(f.authRequired()).toBe(status === 401);
    expect(configuration.error()).toBe('Observed request failure');
  });

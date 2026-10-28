// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonClient, type KoinonTransport, type HttpMethod } from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from '../client-provider';
import { KoinonFacade } from '../koinon-facade';
import { KoinonAccount } from './account';
import { KoinonI18n } from '../foundations/i18n';
const profile = {
  subject: 'person',
  display_name: 'Alex Rivera',
  locale: 'en-US',
  time_zone: 'UTC',
  response_language: 'en',
  avatar_url: null,
  avatar_version: null,
};
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
      KoinonAccount,
      ...provideKoinonClient(new KoinonClient({ transport }), transport),
    ],
  });
  return TestBed.inject(KoinonAccount);
}
describe('personal account preferences', () => {
  it('changes interface preferences only after a successful save', async () => {
    let fail = true;
    const account = setup(async <T>(method: HttpMethod) => {
      if (method === 'PATCH' && fail) throw new Error('Profile is unavailable');
      return (method === 'PATCH' ? { ...profile, locale: 'es-ES' } : profile) as T;
    });
    await account.load();
    expect(await account.save({ locale: 'es-ES' })).toBe(false);
    expect(TestBed.inject(KoinonI18n).text('Library')).toBe('Library');
    fail = false;
    expect(await account.save({ locale: 'es-ES' })).toBe(true);
    expect(TestBed.inject(KoinonI18n).text('Library')).toBe('Biblioteca');
  });
  it('rejects unsupported or oversized avatar files before transport', async () => {
    let calls = 0;
    const account = setup(async <T>() => {
      calls++;
      return profile as T;
    });
    expect(
      await account.uploadAvatar(new File(['bad'], 'avatar.svg', { type: 'image/svg+xml' })),
    ).toBe(false);
    expect(
      await account.uploadAvatar(
        new File([new Uint8Array(2097153)], 'avatar.png', { type: 'image/png' }),
      ),
    ).toBe(false);
    expect(calls).toBe(0);
  });
  it('drops profile responses after the host client changes', async () => {
    let finish!: (value: unknown) => void;
    const account = setup(
      <T>() =>
        new Promise<T>((resolve) => {
          finish = resolve as (value: unknown) => void;
        }),
    );
    const pending = account.load();
    const clients = TestBed.inject((await import('./client-context')).KoinonClientContext);
    clients.bind(
      new KoinonClient({
        transport: {
          request: async <T>() => profile as T,
          stream: () => {
            throw new Error('unused');
          },
        },
      }),
    );
    TestBed.tick();
    finish(profile);
    await pending;
    expect(account.profile()).toBeNull();
  });
});
it('does not replace a newly uploaded avatar with an older in-flight download', async () => {
  const NativeURL = URL;
  vi.stubGlobal(
    'URL',
    class extends NativeURL {
      static override createObjectURL(blob: Blob) {
        return 'blob:' + blob.size;
      }
      static override revokeObjectURL() {
        return;
      }
    },
  );
  try {
    let avatarReads = 0,
      finishOld!: (value: Blob) => void;
    const account = setup(async <T>(method: HttpMethod, path: string) => {
      if (path.endsWith('/avatar') && method === 'GET') {
        avatarReads++;
        return (
          avatarReads === 1
            ? await new Promise<Blob>((resolve) => (finishOld = resolve))
            : new Blob(['new'])
        ) as T;
      }
      return { ...profile, avatar_version: method === 'POST' ? 'v2' : 'v1' } as T;
    });
    const initial = account.load();
    await vi.waitFor(() => expect(avatarReads).toBe(1));
    await account.uploadAvatar(new File(['new'], 'avatar.png', { type: 'image/png' }));
    expect(account.avatar()).toBe('blob:3');
    finishOld(new Blob(['old-photo']));
    await initial;
    expect(account.avatar()).toBe('blob:3');
  } finally {
    vi.unstubAllGlobals();
  }
});

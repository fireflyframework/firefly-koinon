// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonClient, type KoinonTransport, type HttpMethod } from '@fireflyframework/koinon-sdk';
import { provideKoinonClient } from '../client-provider';
import { KoinonFacade } from '../koinon-facade';
import { KoinonPhotoDraft } from './photo-draft';
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
      KoinonPhotoDraft,
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
describe('photo review before upload', () => {
  afterEach(() => vi.unstubAllGlobals());
  function photoSetup() {
    const uploads: Blob[] = [];
    const revoked: string[] = [];
    const NativeURL = URL;
    vi.stubGlobal(
      'URL',
      class extends NativeURL {
        static override createObjectURL() {
          return 'blob:preview';
        }
        static override revokeObjectURL(url: string) {
          revoked.push(url);
        }
      },
    );
    setup(async <T>(method: HttpMethod, path: string, options?: { body?: unknown }) => {
      if (method === 'POST' && path.endsWith('/avatar')) uploads.push(options?.body as Blob);
      return profile as T;
    });
    return { account: TestBed.inject(KoinonPhotoDraft), uploads, revoked };
  }
  it('shows a local preview and cancellation never uploads the selected photo', () => {
    const { account, uploads, revoked } = photoSetup();
    account.stageAvatar(new File(['photo'], 'photo.png', { type: 'image/png' }));
    expect(account.avatarPreview()).toBe('blob:preview');
    account.cancelAvatar();
    expect(account.avatarPreview()).toBe('');
    expect(uploads).toHaveLength(0);
    expect(revoked).toEqual(['blob:preview']);
  });
  it('uploads only after saving and disposes the staged URL', async () => {
    const { account, uploads, revoked } = photoSetup();
    const file = new File(['photo'], 'photo.png', { type: 'image/png' });
    account.stageAvatar(file);
    expect(uploads).toHaveLength(0);
    expect(await account.saveAvatar()).toBe(true);
    expect(uploads).toEqual([file]);
    expect(account.avatarPreview()).toBe('');
    expect(revoked).toContain('blob:preview');
  });
  it('retains the preview when the server rejects the photo', async () => {
    photoSetup();
    const account = TestBed.inject(KoinonPhotoDraft);
    TestBed.inject((await import('./client-context')).KoinonClientContext).bind(
      new KoinonClient({
        transport: {
          request: async () => {
            throw new Error('Image could not be decoded');
          },
          stream: () => {
            throw new Error('Unexpected stream');
          },
        },
      }),
    );
    TestBed.tick();
    account.stageAvatar(new File(['bad'], 'bad.png', { type: 'image/png' }));
    expect(await account.saveAvatar()).toBe(false);
    expect(account.avatarPreview()).toBe('blob:preview');
    expect(account.error()).toContain('decoded');
  });
});
it('disposes a staged private photo when the authenticated account changes', async () => {
  const revoked: string[] = [];
  const NativeURL = URL;
  vi.stubGlobal(
    'URL',
    class extends NativeURL {
      static override createObjectURL() {
        return 'blob:private-preview';
      }
      static override revokeObjectURL(url: string) {
        revoked.push(url);
      }
    },
  );
  try {
    setup(async <T>() => profile as T);
    const account = TestBed.inject(KoinonPhotoDraft);
    account.stageAvatar(new File(['photo'], 'photo.jpg', { type: 'image/jpeg' }));
    TestBed.inject((await import('./client-context')).KoinonClientContext).bind(
      new KoinonClient({
        transport: {
          request: async <T>() => profile as T,
          stream: () => {
            throw new Error('Unexpected stream');
          },
        },
      }),
    );
    TestBed.tick();
    expect(account.avatarPreview()).toBe('');
    expect(revoked).toContain('blob:private-preview');
    expect(await account.saveAvatar()).toBe(false);
  } finally {
    vi.unstubAllGlobals();
  }
});
it('never sends a staged photo to a newly bound account before the identity effect has flushed', async () => {
  const NativeURL = URL;
  let uploads = 0;
  vi.stubGlobal(
    'URL',
    class extends NativeURL {
      static override createObjectURL() {
        return 'blob:previous-account';
      }
      static override revokeObjectURL() {
        return;
      }
    },
  );
  try {
    setup(async <T>() => profile as T);
    const draft = TestBed.inject(KoinonPhotoDraft);
    draft.stageAvatar(new File(['private'], 'private.png', { type: 'image/png' }));
    TestBed.inject((await import('./client-context')).KoinonClientContext).bind(
      new KoinonClient({
        transport: {
          request: async <T>(method: HttpMethod) => {
            if (method === 'POST') uploads++;
            return { ...profile, subject: 'new-account' } as T;
          },
          stream: () => {
            throw new Error('Unexpected stream');
          },
        },
      }),
    );
    expect(await draft.saveAvatar()).toBe(false);
    expect(uploads).toBe(0);
    expect(draft.avatarPreview()).toBe('');
  } finally {
    vi.unstubAllGlobals();
  }
});

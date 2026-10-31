// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { UserProfile } from '@fireflyframework/koinon-sdk';
import type { KoinonAccount } from './account';
import type { KoinonClientContext } from './client-context';
import type { AccountPerformer } from './account-tokens';
export class AccountAvatar {
  private url = '';
  private revision = 0;
  private destroyed = false;
  constructor(
    private readonly clients: KoinonClientContext,
    private readonly contextKey: () => string,
    private readonly state: Pick<KoinonAccount, 'profile' | 'avatar' | 'error'>,
    private readonly accept: (value: UserProfile) => void,
    private readonly perform: AccountPerformer,
  ) {}
  clear() {
    ++this.revision;
    if (this.url) URL.revokeObjectURL(this.url);
    this.url = '';
    this.state.avatar.set('');
  }
  async load(profile: UserProfile) {
    this.clear();
    if (this.destroyed || !profile.avatar_version) return;
    const key = this.contextKey(),
      revision = this.revision;
    try {
      const blob = await this.clients.get().profile.avatar();
      if (
        this.destroyed ||
        key !== this.contextKey() ||
        revision !== this.revision ||
        profile.avatar_version !== this.state.profile()?.avatar_version
      )
        return;
      this.url = URL.createObjectURL(blob);
      this.state.avatar.set(this.url);
    } catch {
      if (!this.destroyed && key === this.contextKey() && revision === this.revision) this.clear();
    }
  }
  async upload(file: File) {
    if (this.destroyed) return false;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2097152) {
      this.state.error.set('Choose a PNG, JPEG or WebP image no larger than 2 MiB.');
      return false;
    }
    const profile = await this.perform(
      () => this.clients.get().profile.uploadAvatar(file),
      this.accept,
      'Profile photo updated.',
    );
    if (profile) await this.load(profile);
    return !!profile;
  }
  async remove() {
    if (this.destroyed) return false;
    return !!(await this.perform(
      () => this.clients.get().profile.deleteAvatar(),
      (profile) => {
        this.accept(profile);
        this.clear();
      },
      'Profile photo removed.',
    ));
  }
  destroy() {
    this.destroyed = true;
    this.clear();
  }
}

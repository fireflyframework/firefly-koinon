// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Injectable, OnDestroy, effect, inject, signal } from '@angular/core';
import { KoinonAccount } from './account';
import { KoinonClientContext } from './client-context';
import { KoinonFacade } from '../koinon-facade';
@Injectable()
export class KoinonPhotoDraft implements OnDestroy {
  private readonly account = inject(KoinonAccount);
  private readonly clients = inject(KoinonClientContext);
  private readonly f = inject(KoinonFacade);
  private key = this.contextKey();
  private stagedAvatar: File | null = null;
  readonly avatarPreview = signal('');
  readonly error = this.account.error;
  constructor() {
    effect(() => this.syncIdentity());
  }
  private syncIdentity() {
    const key = this.contextKey();
    if (key === this.key) return true;
    this.key = key;
    this.cancelAvatar();
    return false;
  }

  private contextKey() {
    return JSON.stringify([this.f.context()?.subject, this.clients.revision()]);
  }
  stageAvatar(file: File) {
    this.syncIdentity();
    if (this.account.pending()) return false;
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type) || file.size > 2097152) {
      this.account.error.set('Choose a PNG, JPEG or WebP image no larger than 2 MiB.');
      return false;
    }
    this.cancelAvatar();
    this.stagedAvatar = file;
    this.avatarPreview.set(URL.createObjectURL(file));
    this.account.error.set('');
    this.account.notice.set('');
    return true;
  }
  cancelAvatar() {
    if (this.avatarPreview()) URL.revokeObjectURL(this.avatarPreview());
    this.avatarPreview.set('');
    this.stagedAvatar = null;
  }
  async saveAvatar() {
    if (!this.syncIdentity()) return false;
    const file = this.stagedAvatar;
    if (!file || this.account.pending()) return false;
    const saved = await this.account.uploadAvatar(file);
    if (!this.syncIdentity()) return false;
    if (saved && this.stagedAvatar === file) this.cancelAvatar();
    return saved;
  }
  ngOnDestroy() {
    this.cancelAvatar();
  }
}

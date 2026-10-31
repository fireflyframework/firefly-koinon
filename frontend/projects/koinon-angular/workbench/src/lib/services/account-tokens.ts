// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { PersonalTokenInput } from '@fireflyframework/koinon-sdk';
import type { KoinonAccount } from './account';
import type { KoinonClientContext } from './client-context';
import type { KoinonFacade } from '../koinon-facade';
export type AccountPerformer = <T>(
  operation: () => Promise<T>,
  apply: ((value: T) => void) | undefined,
  notice?: string,
  tokenScope?: boolean,
) => Promise<T | null>;
export class AccountTokens {
  constructor(
    private readonly clients: KoinonClientContext,
    private readonly f: KoinonFacade,
    private readonly state: Pick<
      KoinonAccount,
      'tokenFilter' | 'tokens' | 'tokenScopes' | 'notice'
    >,
    private readonly perform: AccountPerformer,
    private readonly key: () => string,
  ) {}
  async load(filter: Partial<{ page: number; page_size: number; q: string; status: string }> = {}) {
    const key = this.key();
    this.state.tokenFilter.update((value) => ({ ...value, ...filter }));
    const result = await this.perform(
      () => this.clients.get().tokens.list({ query: this.state.tokenFilter() }),
      (value) => {
        if (key === this.key()) this.state.tokens.set(value);
      },
      '',
      true,
    );
    return key === this.key() ? result : null;
  }
  async scopes() {
    const key = this.key();
    const result = await this.perform(
      () => this.clients.get().tokens.scopes(this.f.tenantId(), this.f.workspaceId() || undefined),
      (value) => {
        if (key === this.key()) this.state.tokenScopes.set(value);
      },
      '',
      true,
    );
    return key === this.key() ? result : null;
  }
  async create(input: PersonalTokenInput) {
    const key = this.key();
    const token = await this.perform(
      () => this.clients.get().tokens.create(input),
      undefined,
      '',
      true,
    );
    if (!token || key !== this.key()) return null;
    await this.load();
    return key === this.key() ? token : null;
  }
  async revoke(id: string) {
    const key = this.key();
    const revoked = await this.perform(
      () => this.clients.get().tokens.revoke(id),
      undefined,
      '',
      true,
    );
    if (revoked === null || key !== this.key()) return false;
    await this.load();
    if (key !== this.key()) return false;
    this.state.notice.set('Token revoked.');
    return true;
  }
}

// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { UserProfile } from '@fireflyframework/koinon-sdk';
import type { KoinonAccount } from './account';
import type { KoinonClientContext } from './client-context';
import type { KoinonFacade } from '../koinon-facade';
import { AccountAvatar } from './account-avatar';
import { AccountTokens, type AccountPerformer } from './account-tokens';
export function createAccountOperations(
  clients: KoinonClientContext,
  facade: KoinonFacade,
  state: Pick<
    KoinonAccount,
    'profile' | 'avatar' | 'error' | 'tokenFilter' | 'tokens' | 'tokenScopes' | 'notice' | 'pending'
  >,
  identity: () => string,
  profileIdentity: () => string,
  accept: (value: UserProfile) => void,
  perform: AccountPerformer,
) {
  return {
    async run<T>(
      operation: () => Promise<T>,
      apply: ((value: T) => void) | undefined,
      notice: string,
      current: () => boolean,
    ): Promise<T | null> {
      try {
        const value = await operation();
        if (!current()) return null;
        apply?.(value);
        state.notice.set(notice);
        return value;
      } catch (error) {
        if (current()) {
          if (error instanceof Error && 'status' in error && error.status === 401)
            facade.authRequired.set(true);
          state.error.set(
            error instanceof Error ? error.message : 'Your account could not be updated.',
          );
        }
        return null;
      } finally {
        if (current()) state.pending.set(false);
      }
    },
    media: new AccountAvatar(clients, profileIdentity, state, accept, perform),
    tokens: new AccountTokens(clients, facade, state, perform, identity),
  };
}
export type AccountOperations = ReturnType<typeof createAccountOperations>;

// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { InjectionToken, type Provider } from '@angular/core';
import type { KoinonClient, KoinonTransport } from '@fireflyframework/koinon-sdk';
export const KOINON_CLIENT = new InjectionToken<KoinonClient>('Koinon client');
export const KOINON_TRANSPORT = new InjectionToken<KoinonTransport>('Koinon transport');
export function provideKoinonClient(client: KoinonClient, transport?: KoinonTransport): Provider[] {
  return [
    { provide: KOINON_CLIENT, useValue: client },
    ...(transport ? [{ provide: KOINON_TRANSPORT, useValue: transport }] : []),
  ];
}

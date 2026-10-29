// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { provideHttpClient, withXsrfConfiguration } from '@angular/common/http';
import { type ApplicationConfig, inject, provideBrowserGlobalErrorListeners } from '@angular/core';
import { FetchTransport, KoinonClient } from '@fireflyframework/koinon-sdk';
import {
  KOINON_CHAT_LOADER,
  KOINON_SETTINGS_LOADER,
  KOINON_INVITATION_LOADER,
  KOINON_SHARED_CONVERSATION_LOADER,
  KOINON_TENANT_RESOLVER,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular/workbench';
import { OrganizationSelection } from './organization-selection';
export function csrfToken(): string | null {
  const value = document.cookie
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith('XSRF-TOKEN='));
  if (!value) return null;
  try {
    return decodeURIComponent(value.slice('XSRF-TOKEN='.length));
  } catch {
    return null;
  }
}
const transport = new FetchTransport({ baseUrl: '/bff/api/v1', credentials: 'include', csrfToken });
export const appConfig: ApplicationConfig = {
  providers: [
    {
      provide: KOINON_TENANT_RESOLVER,
      useFactory: () => {
        const selection = inject(OrganizationSelection);
        return selection.resolve.bind(selection);
      },
    },
    {
      provide: KOINON_SHARED_CONVERSATION_LOADER,
      useValue: () => import('@fireflyframework/koinon-angular/chat/page').then(module => module.KoinonSharedConversation),
    },
    {
      provide: KOINON_INVITATION_LOADER,
      useValue: () =>
        import('@fireflyframework/koinon-angular/settings').then(
          (module) => module.KoinonInvitationAcceptance,
        ),
    },
    {
      provide: KOINON_CHAT_LOADER,
      useValue: () =>
        import('@fireflyframework/koinon-angular/chat/page').then((module) => module.KoinonChatPage),
    },
    {
      provide: KOINON_SETTINGS_LOADER,
      useValue: () =>
        import('@fireflyframework/koinon-angular/settings').then(
          (module) => module.KoinonSettingsPage,
        ),
    },
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(
      withXsrfConfiguration({ cookieName: 'XSRF-TOKEN', headerName: 'X-XSRF-TOKEN' }),
    ),
    ...provideKoinonClient(new KoinonClient({ transport }), transport),
  ],
};

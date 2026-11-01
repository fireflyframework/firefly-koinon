// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// This separate workspace consumes the packed library; it has no source path alias.
import { Component, signal } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { FetchTransport, KoinonClient } from '@fireflyframework/koinon-sdk';
import {
  KOINON_ACTIVITY_LOADER,KOINON_COMMUNICATIONS_LOADER,
  KoinonWorkbench,
  provideKoinonClient,
} from '@fireflyframework/koinon-angular/workbench';
const csrf = () => {
  const part = document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith('XSRF-TOKEN='));
  return part ? decodeURIComponent(part.slice(11)) : null;
};
const transport = new FetchTransport({
  baseUrl: '/bff/api/v1',
  credentials: 'include',
  csrfToken: csrf,
});
const client = new KoinonClient({ transport });
@Component({
  selector: 'consumer-root',
  imports: [KoinonWorkbench],
  template: `<header>
      <h1>External Angular consumer</h1>
      <p>
        The host owns navigation, styling and authentication. The packaged library receives only its
        scoped client and context.
      </p>
      <output id="host-selection">{{ selected() }}</output>
    </header>
    <ffk-workbench
      [client]="client"
      [transport]="transport"
      brandBase="/consumer/assets/brand"
      tenantId="tenant-one"
      workspaceId="workspace-one"
      projectId="project-one"
      [showNavigation]="false"
      (selectionChange)="selected.set($event.name)"
    />`,
})
class Consumer {
  readonly client = client;
  readonly transport = transport;
  readonly selected = signal('Nothing selected');
}
void bootstrapApplication(Consumer, {
  providers: [
    ...provideKoinonClient(client, transport),
    {provide:KOINON_ACTIVITY_LOADER,useValue:()=>import('@fireflyframework/koinon-angular/activity').then(module=>module.KoinonActivityPanel)},
    {
      provide: KOINON_COMMUNICATIONS_LOADER,
      useValue: (kind: 'trigger' | 'center' | 'email') =>
        kind === 'trigger'
          ? import('@fireflyframework/koinon-angular/communications/runtime').then(
              (module) => module.KoinonNotificationCenterTrigger,
            )
          : kind === 'email'
            ? import('@fireflyframework/koinon-angular/communications/invitations').then(
                (module) => module.KoinonEmailInvitationAcceptance,
              )
            : import('@fireflyframework/koinon-angular/communications/inbox').then(
                (module) => module.KoinonNotificationCenter,
              ),
    },
  ],
});

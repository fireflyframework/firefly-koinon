// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// This separate workspace consumes the packed library; it has no source path alias.
import { Component, signal } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { FetchTransport, KoinonClient } from '@fireflyframework/koinon-sdk';
import { KoinonWorkbench, provideKoinonClient } from '@fireflyframework/koinon-angular';
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
      brandBase="/consumer/assets/brand"
      tenantId="tenant-one"
      workspaceId="workspace-one"
      projectId="project-one"
      [showNavigation]="false"
      (selectionChange)="selected.set($event.name)"
    />`,
})
class Consumer {
  readonly selected = signal('Nothing selected');
}
void bootstrapApplication(Consumer, {
  providers: provideKoinonClient(new KoinonClient({ transport }), transport),
});

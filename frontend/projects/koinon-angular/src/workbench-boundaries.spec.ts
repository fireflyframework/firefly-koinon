// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import type { KoinonClient } from '@fireflyframework/koinon-sdk';
import * as legacy from '@fireflyframework/koinon-angular';
import * as workbench from '@fireflyframework/koinon-angular/workbench';
import * as core from '@fireflyframework/koinon-angular/workbench/core';
import * as page from '@fireflyframework/koinon-angular/workbench/page';
import * as panels from '@fireflyframework/koinon-angular/workbench/panels';
import { availabilitySession } from '@fireflyframework/koinon-angular/workbench/availability';
import { availabilitySession as internalSession } from '../workbench/src/lib/services/availability-session';

describe('independent workbench entrypoints', () => {
  it('preserves public service, component and token identities for existing embedders', () => {
    for (const key of [
      'KoinonFacade', 'KoinonClientContext', 'KoinonI18n', 'KoinonTextPipe',
      'KoinonDatePipe', 'KoinonValuePipe', 'KOINON_CLIENT', 'KOINON_TRANSPORT',
      'KOINON_TENANT_RESOLVER', 'provideKoinonClient', 'KoinonButton',
      'KoinonIcon', 'KoinonBadge', 'KoinonSkeleton',
    ] as const) {
      expect(workbench[key]).toBe(core[key]);
      expect(legacy[key]).toBe(core[key]);
      expect(page[key]).toBe(core[key]);
    }
    expect(page.KoinonWorkbench).toBe(workbench.KoinonWorkbench);
    expect(page.KOINON_CHAT_LOADER).toBe(workbench.KOINON_CHAT_LOADER);
    for (const key of ['KoinonInspector', 'KoinonFolderTree', 'KoinonSidePanel', 'KoinonFormField', 'KoinonCodeBlock', 'KoinonCitationPanel'] as const) {
      expect(workbench[key]).toBe(panels[key]);
      expect(legacy[key]).toBe(panels[key]);
    }
  });

  it('shares the client, language and one availability session across entrypoints', () => {
    const client = {} as KoinonClient;
    TestBed.configureTestingModule({providers: [core.KoinonFacade, ...workbench.provideKoinonClient(client)]});
    expect(TestBed.inject(core.KoinonClientContext).get()).toBe(client);
    expect(TestBed.inject(workbench.KoinonClientContext)).toBe(TestBed.inject(core.KoinonClientContext));
    const language = TestBed.inject(core.KoinonI18n);
    core.registerKoinonSpanish({'Independent panel vocabulary': 'Vocabulario del panel independiente'});
    language.apply({locale:'es-ES', time_zone:'UTC', response_language:'es'});
    expect(TestBed.inject(legacy.KoinonI18n).text('Independent panel vocabulary')).toBe('Vocabulario del panel independiente');
    const facade = TestBed.inject(core.KoinonFacade), clients = TestBed.inject(core.KoinonClientContext);
    expect(availabilitySession(facade, clients)).toBe(internalSession(facade, clients));
    expect(availabilitySession(facade, clients)).toBe(availabilitySession(facade, clients));
  });
});

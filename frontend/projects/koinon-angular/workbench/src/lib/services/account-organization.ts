// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { EnvironmentInjector, createEnvironmentInjector } from '@angular/core';
import { KoinonCorporatePresentation } from './corporate-presentation';
import { KoinonOrganizationDirectory } from './organization-directory';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from './client-context';
export function createAccountOrganization(
  parent: EnvironmentInjector,
  facade: KoinonFacade,
  clients: KoinonClientContext,
) {
  const injector = createEnvironmentInjector(
    [
      { provide: KoinonFacade, useValue: facade },
      { provide: KoinonClientContext, useValue: clients },
      KoinonOrganizationDirectory,
      KoinonCorporatePresentation,
    ],
    parent,
  );
  return { state: injector.get(KoinonCorporatePresentation), destroy: () => injector.destroy() };
}
export type AccountOrganization = ReturnType<typeof createAccountOrganization>;

// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import * as legacy from '@fireflyframework/koinon-angular';
import * as workbench from '@fireflyframework/koinon-angular/workbench';
import { SPANISH } from './lib/foundations/spanish';
import { KNOWLEDGE_BEHAVIOR_SPANISH } from '../settings/src/knowledge-behavior-spanish';
import { ORGANIZATION_SPANISH } from '../settings/src/organization-spanish';
import { ORGANIZATION_PROFILE_SPANISH } from '../workbench/src/lib/organisms/organization-spanish';
import { IDENTITY_SPANISH } from '../settings/src/identity-spanish';
import { ACTIVITY_SPANISH } from '../activity/spanish';
describe('published entrypoint compatibility', () => {
  it('preserves class and injection token identity across root and workbench', () => {
    for (const key of [
      'KoinonWorkbench',
      'KoinonI18n',
      'KoinonFacade',
      'KoinonAssistant',
      'KoinonClientContext',
      'KOINON_CLIENT',
      'KOINON_TRANSPORT',
      'KOINON_TENANT_RESOLVER',
    ] as const)
      expect(legacy[key]).toBe(workbench[key]);
  });
  it('keeps the complete existing root translation API synchronous', () => {
    const i18n = TestBed.inject(legacy.KoinonI18n);
    i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'en' });
    for (const [key, translation] of Object.entries(SPANISH))
      expect(i18n.text(key)).toBe(translation);
  });
});

for (const [feature, dictionary] of [
  ['knowledge behavior', KNOWLEDGE_BEHAVIOR_SPANISH],
  ['identity', IDENTITY_SPANISH],
  ['organization settings', ORGANIZATION_SPANISH],
  ['corporate presentation', ORGANIZATION_PROFILE_SPANISH],
  ['knowledge activity', ACTIVITY_SPANISH],
] as const) {
  for (const rootFirst of [true, false]) {
    it(`preserves existing translations when registering ${feature} ${rootFirst ? 'after' : 'before'} root`, () => {
      const i18n = TestBed.inject(workbench.KoinonI18n);
      i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'en' });
      const dictionaries = rootFirst ? [SPANISH, dictionary] : [dictionary, SPANISH];
      try {
        for (const dictionary of dictionaries) workbench.registerKoinonSpanish(dictionary);
        for (const [key, translation] of Object.entries(SPANISH))
          expect(i18n.text(key), key).toBe(translation);
        for (const [key, translation] of Object.entries(dictionary))
          expect(i18n.text(key), key).toBe(translation);
      } finally {
        workbench.registerKoinonSpanish(SPANISH);
      }
    });
  }
}

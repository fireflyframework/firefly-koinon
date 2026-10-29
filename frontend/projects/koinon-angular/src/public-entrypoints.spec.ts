// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import * as legacy from '@fireflyframework/koinon-angular';
import * as workbench from '@fireflyframework/koinon-angular/workbench';
import { SPANISH } from './lib/foundations/spanish';
import { KNOWLEDGE_BEHAVIOR_SPANISH } from '../settings/src/knowledge-behavior-spanish';
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

for (const order of ['root then knowledge behavior', 'knowledge behavior then root']) {
  it(`preserves existing translations when registering ${order}`, () => {
    const i18n = TestBed.inject(workbench.KoinonI18n);
    i18n.apply({ locale: 'es-ES', time_zone: 'UTC', response_language: 'en' });
    const dictionaries = order.startsWith('root')
      ? [SPANISH, KNOWLEDGE_BEHAVIOR_SPANISH]
      : [KNOWLEDGE_BEHAVIOR_SPANISH, SPANISH];
    try {
      for (const dictionary of dictionaries) workbench.registerKoinonSpanish(dictionary);
      for (const [key, translation] of Object.entries(SPANISH))
        expect(i18n.text(key), key).toBe(translation);
      expect(i18n.text('Knowledge behavior')).toBe('Comportamiento del conocimiento');
    } finally {
      workbench.registerKoinonSpanish(SPANISH);
    }
  });
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { DEFAULT_BRANDING, contrast, previewBrandStyles } from './branding-values';
import { applyBrandColor, paletteChecks } from '../../../../settings/src/identity/identity-palette';
it.each(['#ffb34a', '#ffffff', '#000000', '#ffff00', '#2563eb', '#777777'])(
  'derives readable controls and links from brand color %s',
  (color) => {
    const value = applyBrandColor(DEFAULT_BRANDING, color);
    expect(value.palette.light.action).toBe(color);
    for (const theme of ['light', 'dark'] as const) {
      const p = value.palette[theme];
      expect(contrast(p.action, p.action_text)).toBeGreaterThanOrEqual(4.5);
      expect(paletteChecks(p).every((row) => row.passed)).toBe(true);
    }
    expect(DEFAULT_BRANDING.palette.light.action).toBe('#ffb34a');
  },
);
it('shows the actual low-contrast draft in preview while sanitizing invalid CSS colors', () => {
  const value = structuredClone(DEFAULT_BRANDING);
  value.palette.light.text = '#ffffff';
  expect(previewBrandStyles(value, 'light')['--koinon-brand-text']).toBe('#ffffff');
  value.palette.light.action = 'red;display:none';
  expect(previewBrandStyles(value, 'light')['--koinon-brand-action']).toBe('#ffb34a');
});

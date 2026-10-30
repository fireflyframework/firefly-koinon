// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { BrandingValues, BrandingPalette } from '@fireflyframework/koinon-sdk';
import { contrast, resolveBranding } from '@fireflyframework/koinon-angular/workbench';
export function paletteChecks(p: BrandingPalette) {
  return [
    { label: 'Text', ratio: Math.min(contrast(p.text, p.surface), contrast(p.text, p.canvas)) },
    {
      label: 'Secondary text',
      ratio: Math.min(contrast(p.muted, p.surface), contrast(p.muted, p.canvas)),
    },
    {
      label: 'Links & focus',
      ratio: Math.min(contrast(p.accent, p.surface), contrast(p.accent, p.canvas)),
    },
    { label: 'Button text', ratio: contrast(p.action_text, p.action) },
  ].map((row) => ({ ...row, passed: row.ratio >= 4.5 }));
}
function linkColor(color: string, p: BrandingPalette) {
  const channels = [1, 3, 5].map((offset) => parseInt(color.slice(offset, offset + 2), 16));
  for (let step = 0; step <= 255; step++)
    for (const target of [0, 255]) {
      const candidate =
        '#' +
        channels
          .map((c) =>
            Math.round(c + ((target - c) * step) / 255)
              .toString(16)
              .padStart(2, '0'),
          )
          .join('');
      if (Math.min(contrast(candidate, p.surface), contrast(candidate, p.canvas)) >= 4.55)
        return candidate;
    }
  throw new Error(
    'The current backgrounds do not support a readable link color. Review the background colors first.',
  );
}
export function applyBrandColor(values: BrandingValues, color: string) {
  if (!/^#[a-f0-9]{6}$/i.test(color)) throw new Error('Enter a six-digit hex color.');
  const value = resolveBranding(values);
  const actionText =
    contrast(color, '#10110f') >= 4.5
      ? '#10110f'
      : contrast(color, '#ffffff') >= 4.5
        ? '#ffffff'
        : '#000000';
  return {
    ...value,
    palette: Object.fromEntries(
      (['light', 'dark'] as const).map((theme) => [
        theme,
        {
          ...value.palette[theme],
          action: color.toLowerCase(),
          action_text: actionText,
          accent: linkColor(color, value.palette[theme]),
        },
      ]),
    ) as typeof value.palette,
  };
}

// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { BrandingValues } from '@fireflyframework/koinon-sdk';
import { DEFAULT_BRANDING, PALETTE_FIELDS, resolveBranding } from '@fireflyframework/koinon-angular/workbench/startup';
const hex = /^#[a-f\d]{6}$/i;

export function previewBrandStyles(
  value: BrandingValues,
  theme: 'light' | 'dark',
): Record<string, string> {
  const resolved = resolveBranding(value),
    styles: Record<string, string> = {};
  for (const mode of ['light', 'dark'] as const)
    for (const key of PALETTE_FIELDS) {
      const color = resolved.palette[mode][key];
      styles[`--koinon-brand-${mode}-${key}`] = hex.test(color)
        ? color
        : DEFAULT_BRANDING.palette[mode][key];
    }
  for (const key of PALETTE_FIELDS)
    styles[`--koinon-brand-${key}`] = styles[`--koinon-brand-${theme}-${key}`];
  return styles;
}

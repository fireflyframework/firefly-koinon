// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { BrandingValues, BrandingPalette } from '@fireflyframework/koinon-sdk';
export type ResolvedBranding = Required<Omit<BrandingValues, 'palette'>> & {
  palette: { light: BrandingPalette; dark: BrandingPalette };
};
export const DEFAULT_BRANDING: ResolvedBranding = {
  product_name: 'koinon',
  assistant_name: 'koinon',
  font_family: 'Manrope',
  logo_light: null,
  logo_dark: null,
  symbol: null,
  favicon: null,
  palette: {
    light: {
      surface: '#ffffff',
      canvas: '#f3f1eb',
      text: '#272820',
      muted: '#62645b',
      line: '#d8d4ca',
      action: '#ffb34a',
      action_text: '#10110f',
      accent: '#855414',
    },
    dark: {
      surface: '#1d1f1a',
      canvas: '#10110f',
      text: '#f3f1eb',
      muted: '#bfb8ab',
      line: '#474a42',
      action: '#ffb34a',
      action_text: '#10110f',
      accent: '#ffb34a',
    },
  },
};
export function resolveBranding(value: BrandingValues): ResolvedBranding {
  return {
    ...DEFAULT_BRANDING,
    ...value,
    palette: {
      light: { ...DEFAULT_BRANDING.palette.light, ...value.palette?.light },
      dark: { ...DEFAULT_BRANDING.palette.dark, ...value.palette?.dark },
    },
  };
}
export const PALETTE_FIELDS = [
  'surface',
  'canvas',
  'text',
  'muted',
  'line',
  'action',
  'action_text',
  'accent',
] as const;
const hex = /^#[a-f\d]{6}$/i;
function luminance(color: string) {
  return [1, 3, 5]
    .map((index) => parseInt(color.slice(index, index + 2), 16) / 255)
    .map((value) => (value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4))
    .reduce((sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index], 0);
}
export function contrast(first: string, second: string) {
  if (!hex.test(first) || !hex.test(second)) return 0;
  const a = luminance(first),
    b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
export function validateBranding(value: BrandingValues): string[] {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return ['Provide a branding settings object.'];
  if (
    Object.keys(value).some(
      (key) =>
        ![
          'product_name',
          'assistant_name',
          'logo_light',
          'logo_dark',
          'symbol',
          'favicon',
          'palette',
          'font_family',
        ].includes(key),
    )
  )
    return ['Provide a branding settings object.'];
  if (value.font_family !== undefined && !['Manrope', 'Inter'].includes(value.font_family))
    return ['Choose Manrope or Inter.'];
  value = resolveBranding(value);
  const errors: string[] = [];
  for (const key of ['product_name', 'assistant_name'] as const)
    if (
      typeof value[key] !== 'string' ||
      !value[key].trim() ||
      Array.from(value[key]).length > 64 ||
      Array.from(value[key]!).some(
        (char) => char !== ' ' && /[\p{C}\p{Z}]/u.test(char) && !/\p{Co}/u.test(char),
      )
    )
      errors.push('Enter a name with 1 to 64 printable characters.');
  for (const key of ['logo_light', 'logo_dark', 'symbol', 'favicon'] as const)
    if (
      value[key] !== null &&
      (typeof value[key] !== 'string' ||
        !/^data:image\/(png|jpeg|webp);base64,[A-Za-z\d+/]+=*$/.test(value[key]!) ||
        value[key]!.length > 349550)
    )
      errors.push('Choose a PNG, JPEG or WebP image up to 256 KB.');
  for (const theme of ['light', 'dark'] as const) {
    const p = value.palette?.[theme];
    if (!p || PALETTE_FIELDS.some((key) => !hex.test(p[key]))) {
      errors.push('Use a six-digit hex color for every palette field.');
      continue;
    }
    if (
      contrast(p.text, p.surface) < 4.5 ||
      contrast(p.text, p.canvas) < 4.5 ||
      contrast(p.muted, p.surface) < 4.5 ||
      contrast(p.muted, p.canvas) < 4.5
    )
      errors.push(
        'Text and secondary text need a contrast ratio of at least 4.5:1 on both backgrounds.',
      );
    if (contrast(p.action_text, p.action) < 4.5)
      errors.push('Button text needs a contrast ratio of at least 4.5:1.');
    if (contrast(p.accent, p.surface) < 4.5 || contrast(p.accent, p.canvas) < 4.5)
      errors.push('Links and focus indicators need a contrast ratio of at least 4.5:1.');
  }
  return [...new Set(errors)];
}
export function brandStyles(
  value: BrandingValues,
  theme: 'light' | 'dark',
): Record<string, string> {
  const resolved = resolveBranding(value);
  const styles: Record<string, string> = {};
  if (validateBranding(value).length) return brandStyles(DEFAULT_BRANDING, theme);
  for (const mode of ['light', 'dark'] as const)
    for (const key of PALETTE_FIELDS)
      styles[`--koinon-brand-${mode}-${key}`] = resolved.palette[mode][key];
  for (const key of PALETTE_FIELDS) styles[`--koinon-brand-${key}`] = resolved.palette[theme][key];
  return styles;
}
export function brandImage(value: BrandingValues, theme: 'light' | 'dark', base: string) {
  return (
    value[theme === 'dark' ? 'logo_dark' : 'logo_light'] ||
    value.logo_light ||
    value.logo_dark ||
    (value.product_name === 'koinon'
      ? base + '/logos/firefly-koinon-lockup-' + (theme === 'dark' ? 'reversed' : 'color') + '.svg'
      : '')
  );
}
export function brandSymbol(value: BrandingValues, base: string) {
  return (
    value.symbol ||
    (value.assistant_name === 'koinon' ? base + '/logos/koinon-symbol-color.svg' : '')
  );
}

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

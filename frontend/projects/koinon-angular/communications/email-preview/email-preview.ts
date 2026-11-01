// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  Component,
  Input,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
registerKoinonSpanish({
  'Email preview': 'Vista previa del correo',
  Preview: 'Vista previa',
  From: 'De',
  Subject: 'Asunto',
  'Email format': 'Formato del correo',
  'Plain text': 'Texto sin formato',
  'Rendered email preview': 'Vista previa del correo generado',
  'Links are disabled in this email preview.':
    'Los enlaces están desactivados en esta vista previa.',
});
import { KoinonRenderedEmail } from './rendered-email';
import { NgStyle } from '@angular/common';
import { KoinonBadge, KoinonTextPipe } from '@fireflyframework/koinon-angular';
import {
  KoinonFontLoader,
  brandImage,
  brandStyles,
  resolveBranding,
  validateBranding,
} from '@fireflyframework/koinon-angular/workbench';
import type { CommunicationEmailPreview } from '@fireflyframework/koinon-angular/communications';
@Component({
  selector: 'ffk-email-preview',
  imports: [KoinonRenderedEmail, NgStyle, KoinonBadge, KoinonTextPipe],
  providers: [KoinonFontLoader],
  templateUrl: './email-preview.html',
  styleUrl: './email-preview.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonEmailPreview {
  @Input({ required: true }) set value(value: CommunicationEmailPreview) {
    this.preview.set(value);
  }
  @Input() set brandBase(value: string) {
    this.assetBase.set(value);
  }
  readonly tab = signal<'html' | 'text'>('html');
  readonly year = new Date().getUTCFullYear();
  readonly preview = signal<CommunicationEmailPreview | null>(null);
  private readonly assetBase = signal('/assets/brand');
  private readonly font = inject(KoinonFontLoader);
  readonly identity = computed(() => {
    const preview = this.preview();
    const value = preview?.branding ?? {
      product_name: preview?.product_name ?? preview?.sender_name ?? 'koinon',
    };
    return resolveBranding(validateBranding(value).length ? {} : value);
  });
  readonly styles = computed(() => brandStyles(this.identity(), 'light'));
  readonly logo = computed(() => brandImage(this.identity(), 'light', this.assetBase()));
  constructor() {
    effect(() => {
      if (this.preview()) void this.font.load(this.assetBase(), this.identity().font_family);
    });
  }
}

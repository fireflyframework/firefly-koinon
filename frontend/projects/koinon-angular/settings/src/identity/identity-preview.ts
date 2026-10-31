// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  Component,
  ChangeDetectionStrategy,
  Input,
  Output,
  EventEmitter,
  computed,
  signal,
} from '@angular/core';
import { NgStyle } from '@angular/common';
import { KoinonIcon, KoinonTextPipe } from '@fireflyframework/koinon-angular';
import {
  resolveBranding,
  brandImage,
  brandSymbol,
  previewBrandStyles,
} from '@fireflyframework/koinon-angular/workbench';
import type { BrandingValues } from '@fireflyframework/koinon-sdk';
export type IdentitySurface = 'navigation' | 'chat' | 'sign-in';
@Component({
  selector: 'ffk-identity-preview',
  imports: [NgStyle, KoinonIcon, KoinonTextPipe],
  templateUrl: './identity-preview.html',
  styleUrl: './identity-preview.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonIdentityPreview {
  @Input({ required: true }) set value(value: BrandingValues) {
    this.identity.set(resolveBranding(value));
  }
  @Input() set deployment(value: BrandingValues) {
    this.installation.set(resolveBranding(value));
  }
  @Input() set theme(value: 'light' | 'dark') {
    this.mode.set(value);
  }
  @Input() installationReady = false;
  @Input() brandBase = '/assets/brand';
  @Output() themeChanged = new EventEmitter<'light' | 'dark'>();
  readonly identity = signal(resolveBranding({}));
  readonly installation = signal(resolveBranding({}));
  readonly mode = signal<'light' | 'dark'>('light');
  readonly surface = signal<IdentitySurface>('chat');
  readonly valueShown = computed(() =>
    this.surface() === 'sign-in' ? this.installation() : this.identity(),
  );
  readonly styles = computed(() => previewBrandStyles(this.valueShown(), this.mode()));
  logo() {
    return brandImage(this.valueShown(), this.mode(), this.brandBase);
  }
  symbol() {
    return brandSymbol(this.valueShown(), this.brandBase);
  }
  readonly surfaces: { id: IdentitySurface; label: string; icon: string }[] = [
    { id: 'chat', label: 'Chat', icon: 'chat' },
    { id: 'navigation', label: 'Navigation', icon: 'grid' },
    { id: 'sign-in', label: 'Sign-in', icon: 'logout' },
  ];
}

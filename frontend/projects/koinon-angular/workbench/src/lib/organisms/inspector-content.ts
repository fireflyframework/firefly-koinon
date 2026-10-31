// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { KoinonTextPipe, KoinonDatePipe } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonBadge } from '../atoms/badge';
import { KoinonIcon } from '../atoms/icon';
import type { KoinonInspector } from './inspector';
@Component({
  selector: 'ffk-inspector-content',
  imports: [KoinonTextPipe, KoinonDatePipe, CdkTrapFocus, KoinonButton, KoinonBadge, KoinonIcon],
  templateUrl: './inspector-content.html',
  styleUrl: './inspector.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonInspectorContent {
  @Input({ required: true }) view!: KoinonInspector;
}

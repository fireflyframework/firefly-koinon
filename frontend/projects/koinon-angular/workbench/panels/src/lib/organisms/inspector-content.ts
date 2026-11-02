// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { KoinonTextPipe, KoinonDatePipe } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonKnowledgeAvailability } from '@fireflyframework/koinon-angular/workbench/availability';
import { KoinonButton } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonBadge } from '@fireflyframework/koinon-angular/workbench/core';
import { KoinonIcon } from '@fireflyframework/koinon-angular/workbench/core';
import type { KoinonInspector } from './inspector';
@Component({
  selector: 'ffk-inspector-content',
  imports: [KoinonTextPipe, KoinonDatePipe, CdkTrapFocus, KoinonButton, KoinonBadge, KoinonIcon, KoinonKnowledgeAvailability],
  templateUrl: './inspector-content.html',
  styleUrl: './inspector.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonInspectorContent {
  @Input({ required: true }) view!: KoinonInspector;
}

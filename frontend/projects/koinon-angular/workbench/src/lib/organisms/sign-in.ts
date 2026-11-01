// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { KoinonTextPipe } from '../foundations/i18n';
import { KoinonButton } from '../atoms/button';
import { KoinonIcon } from '../atoms/icon';
import { KoinonPoweredBy } from '../atoms/powered-by';
@Component({
  selector: 'ffk-sign-in',
  imports: [KoinonTextPipe, KoinonButton, KoinonIcon, KoinonPoweredBy],
  templateUrl: './sign-in.html',
  styleUrl: './sign-in.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonSignIn {
  @Input() productName = 'koinon';
  @Input() logo = '';
  @Input() symbol = '';
  @Input() customBrand = false;
  @Input() brandBase = '/assets/brand';
  @Input() theme: 'light' | 'dark' = 'light';
  @Input() sessionEnded = false;
  @Output() authenticationRequired = new EventEmitter<void>();
  @Output() themeChanged = new EventEmitter<'light' | 'dark'>();
}

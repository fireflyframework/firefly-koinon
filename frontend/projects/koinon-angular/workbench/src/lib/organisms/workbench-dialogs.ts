// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {registerKoinonSpanish} from '../foundations/i18n';
import {PANEL_SPANISH} from '../foundations/panel-spanish.generated';
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { DecimalPipe, JsonPipe } from '@angular/common';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import type { KoinonWorkbench } from '../koinon-angular';
import { KoinonTextPipe } from '../foundations/i18n';
import { KoinonAccountPanel } from './account-panel';
import { KoinonFolderTree } from './folder-tree';
import { KoinonCodeBlock } from '../atoms/code-block';
import { KoinonButton } from '../atoms/button';
import { KoinonIcon } from '../atoms/icon';
import { KoinonBadge } from '../atoms/badge';
import { KoinonSkeleton } from '../atoms/skeleton';
import { KoinonFormField } from '../molecules/form-field';
import { KoinonCitationPanel } from '../citation-panel';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonSearchField } from '../molecules/search-field';
registerKoinonSpanish(PANEL_SPANISH);
@Component({
  selector: 'ffk-workbench-dialogs',
  imports: [
    DecimalPipe,
    JsonPipe,
    CdkTrapFocus,
    KoinonTextPipe,
    KoinonAccountPanel,
    KoinonFolderTree,
    KoinonCodeBlock,
    KoinonButton,
    KoinonIcon,
    KoinonBadge,
    KoinonSkeleton,
    KoinonFormField,
    KoinonCitationPanel,
    KoinonPagination,
    KoinonSearchField,
  ],
  templateUrl: './workbench-dialogs.html',
  styleUrl: './workbench-dialogs.scss',
  host: { style: 'display:contents' },
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonWorkbenchDialogs {
  @Input({ required: true }) w!: KoinonWorkbench;
}

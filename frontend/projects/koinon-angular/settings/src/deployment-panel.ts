// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { Component, Input, ChangeDetectionStrategy } from '@angular/core';
import type { DeploymentConfiguration, ResourceObservation } from '@fireflyframework/koinon-sdk';
import {
  KoinonBadge,
  KoinonTextPipe,
  KoinonDatePipe,
  KoinonValuePipe,
} from '@fireflyframework/koinon-angular';
export function observationLabel(value: Pick<ResourceObservation, 'available'>) {
  return value.available === true
    ? 'Available'
    : value.available === false
      ? 'Needs attention'
      : 'Not checked';
}
@Component({
  selector: 'ffk-deployment-panel',
  imports: [KoinonBadge, KoinonTextPipe, KoinonDatePipe, KoinonValuePipe],
  templateUrl: './deployment-panel.html',
  styleUrl: './deployment-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonDeploymentPanel {
  @Input() deployment: DeploymentConfiguration | undefined;
  @Input() workspaceNames: Record<string, string> = {};
  readonly label = observationLabel;
  datasourceName(id: string) {
    return (
      (
        {
          primary: 'Catalog database',
          canon: 'Document database',
          canon_admin: 'Document provisioning',
          structured: 'Dataset database',
          structured_admin: 'Dataset provisioning',
        } as Record<string, string>
      )[id] ?? id
    );
  }
  storageName(id: string) {
    return id === 'documents' ? 'Documents' : id === 'structured' ? 'Datasets' : id;
  }
  backendName(backend: string | null | undefined) {
    return (
      (
        {
          local: 'Local storage',
          localfs: 'Local storage',
          s3: 'Amazon S3',
          gcs: 'Google Cloud Storage',
          azure: 'Azure Blob Storage',
        } as Record<string, string>
      )[backend ?? ''] ??
      backend ??
      'Not reported'
    );
  }
  workspaceName(id: string | undefined) {
    return id ? (this.workspaceNames[id] ?? 'Selected space') : '';
  }
}

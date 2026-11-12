// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type { SourceConnectionOutput } from '@fireflyframework/koinon-sdk/content-sources';
export const providerName = (provider: string) =>
  ({ google_drive: 'Google Drive', onedrive: 'OneDrive', sharepoint: 'SharePoint' })[provider] ??
  'Connected account';
export const connectionStatus = (status: SourceConnectionOutput['status']) =>
  ({
    connected: 'Connected',
    pending: 'Waiting for account connection…',
    reconnect_required: 'Reconnect required',
    disconnected: 'Disconnected',
  })[status];

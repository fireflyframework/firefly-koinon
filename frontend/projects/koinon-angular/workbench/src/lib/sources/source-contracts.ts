// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type {
  SourceConnectionOutput,
  SourceConnectionPage,
} from '@fireflyframework/koinon-sdk/content-sources';
export type SourceProvider = SourceConnectionOutput['provider'];
export interface SourceCapabilities {
  accounts_available: boolean;
  inbound_only: true;
  synchronization_available: boolean;
  providers: {
    provider: SourceProvider;
    display_name: string;
    consent_available: boolean;
    unavailable_reason: 'disabled' | 'not_configured' | null;
  }[];
  modes: ('document' | 'dataset')[];
  formats: { extension: string; mode: 'document' | 'dataset' }[];
  schedule: {
    min_interval_seconds: number;
    max_interval_seconds: number;
    calendar_timezones: 'iana';
    max_calendar_weekdays: 7;
  };
}
export interface SourceConnection extends Omit<
  SourceConnectionOutput,
  'synchronization_available'
> {
  synchronization_available?: boolean;
  display_name?: string | null;
  display_address?: string | null;
  display_address_verified?: boolean;
}
export interface ConnectionPage extends Omit<
  SourceConnectionPage,
  'items' | 'synchronization_available'
> {
  items: SourceConnection[];
  synchronization_available?: boolean;
}
export interface SourceAuthorization {
  connection_id: string;
  challenge_id: string;
  authorization_url: string;
  expires_at: string;
  callback_uri: string;
}

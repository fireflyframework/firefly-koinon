// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import type { Capabilities, KnowledgeRole } from '@fireflyframework/koinon-sdk';
export type KnowledgeSettingsSection = 'providers' | 'storage' | 'agents';
export interface KnowledgeSectionRequest {
  section: KnowledgeSettingsSection;
  workspaceId: string | null;
  domain: KnowledgeRole['domain'] | null;
}
export function knowledgeDomainRegistered(
  capabilities: Capabilities | null,
  domain: KnowledgeRole['domain'],
) {
  const current = capabilities?.domains?.[domain === 'documents' ? 'canon' : 'structured'];
  return current?.installed === true && current.registered === true;
}

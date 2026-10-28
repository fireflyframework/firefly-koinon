// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import type {
  KnowledgeConnectionInput,
  KnowledgeRole,
  ModelParameters,
} from '@fireflyframework/koinon-sdk';
export interface KnowledgeFormValues {
  mode: 'provider' | 'current_agent';
  provider_id: string;
  model_id: string;
  enabled: boolean;
  dimensions: string;
  storage_dimensions: string;
  space_id: string;
}
export function connectionInput(
  role: KnowledgeRole,
  workspace: string,
  value: KnowledgeFormValues,
  options: ModelParameters = {},
): { input?: KnowledgeConnectionInput; errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const input: KnowledgeConnectionInput = {
    domain: role.domain,
    role: role.id,
    workspace_id: workspace || null,
    mode: value.mode,
    enabled: value.enabled,
  };
  if (value.mode === 'current_agent') {
    if (!role.supports_current_agent || role.kind === 'embedding')
      errors['mode'] = 'Choose a separate provider for this role.';
  } else {
    if (!value.provider_id) errors['provider_id'] = 'Choose a provider.';
    if (!value.model_id) errors['model_id'] = 'Choose a model.';
    input.provider_id = value.provider_id;
    input.model_id = value.model_id;
    input.model_options = role.kind === 'embedding' ? {} : options;
    if (role.kind === 'embedding') {
      for (const name of ['dimensions', 'storage_dimensions'] as const) {
        const number = Number(value[name]);
        if (!/^\d+$/.test(value[name]) || !Number.isInteger(number) || number < 1 || number > 4096)
          errors[name] = 'Enter a whole number from 1 to 4096.';
        else input[name] = number;
      }
      if (!value.space_id.trim())
        errors['space_id'] = 'Enter the approved reference for an existing compatible index.';
      else if (value.space_id.trim().length > 256)
        errors['space_id'] = 'The index reference must contain at most 256 characters.';
      else input.space_id = value.space_id.trim();
      if (
        input.dimensions &&
        input.storage_dimensions &&
        input.dimensions > input.storage_dimensions
      )
        errors['dimensions'] = 'Model dimensions cannot exceed storage dimensions.';
      if (role.domain === 'documents' && input.dimensions !== input.storage_dimensions)
        errors['storage_dimensions'] = 'Document model and storage dimensions must match.';
      if (role.domain === 'structured' && input.storage_dimensions !== 1536)
        errors['storage_dimensions'] = 'Dataset indexes require 1536 storage dimensions.';
    }
  }
  return Object.keys(errors).length ? { errors } : { input, errors };
}

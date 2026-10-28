// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { connectionInput } from '../../../settings/src/knowledge-form';
import type { KnowledgeRole } from '@fireflyframework/koinon-sdk';
const embedding: KnowledgeRole = {
  id: 'documents.embedding',
  domain: 'documents',
  label: 'Document embeddings',
  kind: 'embedding',
  purposes: ['search'],
  supports_current_agent: false,
  compatible_index_required: true,
  assignment: null,
  status: 'needs_setup',
  runtime_qualification: 'not_run',
};
const values = {
  mode: 'provider' as const,
  provider_id: 'provider',
  model_id: 'model',
  enabled: true,
  dimensions: '768',
  storage_dimensions: '768',
  space_id: 'approved-index',
};
describe('knowledge assignment form constraints', () => {
  it('requires an explicit compatible index instead of guessing one', () => {
    expect(
      connectionInput(embedding, '', { ...values, space_id: '' }).errors['space_id'],
    ).toBeTruthy();
    expect(
      connectionInput(embedding, '', { ...values, storage_dimensions: '1536' }).errors[
        'storage_dimensions'
      ],
    ).toBeTruthy();
    expect(
      connectionInput(embedding, '', { ...values, dimensions: '768.5' }).errors['dimensions'],
    ).toBeTruthy();
    expect(connectionInput(embedding, '', values).input).toEqual({
      domain: 'documents',
      role: 'documents.embedding',
      workspace_id: null,
      mode: 'provider',
      provider_id: 'provider',
      model_id: 'model',
      enabled: true,
      model_options: {},
      dimensions: 768,
      storage_dimensions: 768,
      space_id: 'approved-index',
    });
  });
  it('rejects current-agent mode for embeddings and permits it only by descriptor', () => {
    expect(
      connectionInput(embedding, 'workspace', { ...values, mode: 'current_agent' }).errors['mode'],
    ).toBeTruthy();
    const role = {
      ...embedding,
      id: 'documents.answer',
      kind: 'generative' as const,
      supports_current_agent: true,
    };
    expect(connectionInput(role, 'workspace', { ...values, mode: 'current_agent' }).input).toEqual({
      domain: 'documents',
      role: 'documents.answer',
      workspace_id: 'workspace',
      mode: 'current_agent',
      enabled: true,
    });
  });
  it('requires structured storage width1536 without choosing the model or space', () => {
    const role = { ...embedding, id: 'structured.embedding', domain: 'structured' as const };
    expect(connectionInput(role, '', values).errors['storage_dimensions']).toBeTruthy();
    expect(
      connectionInput(role, '', { ...values, storage_dimensions: '1536' }).input
        ?.storage_dimensions,
    ).toBe(1536);
  });
});

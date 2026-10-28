// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { describe, it, expect } from 'vitest';
import { createLibrary, defineComponent } from '@openuidev/lang-core';
import {
  answerProps,
  evidenceProps,
  validateEvidenceLanguage,
} from '../../../chat/evidence/src/openui/evidence-language';
const library = createLibrary({
  components: [
    defineComponent({
      name: 'KnowledgeAnswer',
      description: 'Evidence',
      props: answerProps,
      component: null,
    }),
    defineComponent({
      name: 'Evidence',
      description: 'Reference',
      props: evidenceProps,
      component: null,
    }),
  ],
  root: 'KnowledgeAnswer',
});
const schema = library.toJSONSchema();
describe('registered evidence language boundary', () => {
  it('filters supporting results before loading primary cards while still rejecting unsafe components', () => {
    const source =
      'root = KnowledgeAnswer([query, schema])\nquery = Evidence("q", "chart")\nschema = Evidence("s", "schema")';
    const primary = validateEvidenceLanguage(source, false, schema, ['q']);
    expect(primary.source).toContain('Evidence("q", "auto")');
    expect(primary.source).not.toContain('Evidence("s"');
    expect(validateEvidenceLanguage(source, false, schema, []).source).not.toContain('Evidence(');
    expect(
      validateEvidenceLanguage(
        'root = KnowledgeAnswer([item])\nitem = Html("unsafe")',
        false,
        schema,
        [],
      ).status,
    ).toBe('error');
  });
  it('normalizes legacy layouts to one canonical view per result without merging distinct results', () => {
    const result = validateEvidenceLanguage(
      'root = KnowledgeAnswer([table, chart, sources])\ntable = Evidence("result-1", "table")\nchart = Evidence("result-1", "chart")\nsources = Evidence("result-2", "citations")',
      false,
      schema,
    );
    expect(result.status).toBe('ready');
    expect(result.source.match(/Evidence\(/g)).toHaveLength(2);
    expect(result.source).toContain('Evidence("result-1", "auto")');
    expect(result.source).toContain('Evidence("result-2", "auto")');
  });
  it('accepts canonical evidence references and emits a safe renderer program', () => {
    const result = validateEvidenceLanguage(
      'root = KnowledgeAnswer([table])\ntable = Evidence("result-1", "table")',
      false,
      schema,
    );
    expect(result.status).toBe('ready');
    expect(result.source).toContain('Evidence("result-1", "auto")');
  });
  for (const source of [
    'root = KnowledgeAnswer([item])\nitem = Html("<img src=x onerror=alert(1)>")',
    'root = KnowledgeAnswer([])\nq = Query("arbitrary_network")',
    'root = KnowledgeAnswer([])\nm = Mutation("change_access")',
    'root = KnowledgeAnswer([item])\n$id = "result-1"\nitem = Evidence($id,"table")',
  ])
    it('rejects unsupported execution or components: ' + source.split('\n').at(-1), () => {
      expect(validateEvidenceLanguage(source, false, schema).status).toBe('error');
    });
  it('waits for incomplete streamed references without rendering partial IDs', () => {
    const result = validateEvidenceLanguage(
      'root = KnowledgeAnswer([item])\nitem = Evidence("res',
      true,
      schema,
    );
    expect(result.status).toBe('pending');
    expect(result.source).toBe('');
  });
  it('rejects incomplete final artifacts and external URL references', () => {
    expect(
      validateEvidenceLanguage('root = KnowledgeAnswer([missing])', false, schema).status,
    ).toBe('error');
    expect(
      validateEvidenceLanguage(
        'root = KnowledgeAnswer([e])\ne = Evidence("https://example.com", "table")',
        false,
        schema,
      ).status,
    ).toBe('error');
  });
});

// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { createParser, type LibraryJSONSchema, type ElementNode } from '@openuidev/lang-core';
import { z } from 'zod/v4';
export const answerProps = z.object({ children: z.array(z.unknown()).max(32) }).strict();
export const evidenceProps = z
  .object({
    resultId: z
      .string()
      .min(1)
      .max(128)
      .regex(/^[A-Za-z0-9][A-Za-z0-9._:-]*$/),
    view: z
      .enum(['auto', 'table', 'chart', 'document', 'schema', 'lineage', 'citations', 'proposal'])
      .optional(),
  })
  .strict();
export type EvidenceView = z.infer<typeof evidenceProps>['view'];
export interface EvidenceLanguage {
  status: 'ready' | 'pending' | 'error';
  source: string;
  message?: string;
}
export function validateEvidenceLanguage(
  source: string,
  streaming: boolean,
  schema: LibraryJSONSchema,
  resultIds?: readonly string[],
): EvidenceLanguage {
  const error = (
    message = 'This answer contains an unsupported evidence view.',
  ): EvidenceLanguage => ({ status: 'error', source: '', message });
  const pending: EvidenceLanguage = { status: 'pending', source: '' };
  if (!source.trim()) return streaming ? pending : error('This answer has no evidence view.');
  if (source.length > 65536) return error('This evidence view exceeds the supported size.');
  try {
    const parsed = createParser(schema).parse(source);
    if (
      parsed.queryStatements.length ||
      parsed.mutationStatements.length ||
      Object.keys(parsed.stateDeclarations).length
    )
      return error('This evidence view requested an unsupported action.');
    if (parsed.meta.errors.length) return streaming && parsed.meta.incomplete ? pending : error();
    if (parsed.meta.unresolved.length || parsed.meta.incomplete)
      return streaming ? pending : error('This evidence view is incomplete.');
    if (parsed.meta.orphaned.length || !parsed.root || parsed.root.typeName !== 'KnowledgeAnswer')
      return error();
    const root = answerProps.safeParse(parsed.root.props);
    if (!root.success) return error();
    const leaves: { resultId: string; view: EvidenceView }[] = [];
    for (const value of root.data.children) {
      const node = value as Partial<ElementNode> | null;
      if (!node || node.type !== 'element' || node.typeName !== 'Evidence') return error();
      if (node.partial)
        return streaming ? pending : error('This evidence reference is incomplete.');
      const props = evidenceProps.safeParse(node.props);
      if (!props.success) return error();
      leaves.push({ resultId: props.data.resultId, view: props.data.view ?? 'auto' });
    }
    // Rebuild only static allowlisted nodes so renderer evaluation never receives model expressions.
    const canonical = [...new Map(leaves.map((leaf) => [leaf.resultId, leaf])).values()].filter(
      (leaf) => resultIds === undefined || resultIds.includes(leaf.resultId),
    );
    const ids = canonical.map((_, index) => 'e' + index);
    return {
      status: 'ready',
      source:
        'root = KnowledgeAnswer([' +
        ids.join(', ') +
        '])\n' +
        canonical
          .map(
            (leaf, index) => `${ids[index]} = Evidence(${JSON.stringify(leaf.resultId)}, "auto")`,
          )
          .join('\n'),
    };
  } catch {
    return streaming ? pending : error('This evidence view could not be read.');
  }
}

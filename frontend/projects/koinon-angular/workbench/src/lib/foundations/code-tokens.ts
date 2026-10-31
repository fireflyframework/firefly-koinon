// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export interface CodeToken {
  kind: string;
  text: string;
}
interface HighlightNode {
  type: string;
  value?: unknown;
  properties?: { className?: unknown };
  children?: readonly HighlightNode[];
}
let highlighter: Promise<ReturnType<typeof import('lowlight').createLowlight>> | undefined;
const tokenStyles: Readonly<Record<string, string>> = {
  'hljs-keyword': 'keyword',
  'hljs-name': 'keyword',
  'hljs-literal': 'keyword',
  'hljs-selector-tag': 'keyword',
  'hljs-string': 'string',
  'hljs-regexp': 'string',
  'hljs-attr': 'string',
  'hljs-comment': 'comment',
  'hljs-number': 'number',
  'hljs-built_in': 'parameter',
  'hljs-title': 'parameter',
};

export async function codeTokens(code: string, language: string): Promise<readonly CodeToken[]> {
  const plain = [{ kind: 'plain', text: code }];
  if (!language || ['text', 'plaintext', 'txt'].includes(language) || code.length > 131072)
    return plain;
  try {
    highlighter ??= import('lowlight').then(({ common, createLowlight }) => createLowlight(common));
    const grammar = await highlighter;
    if (!grammar.registered(language)) return plain;
    const tokens: CodeToken[] = [];
    const visit = (node: HighlightNode, inherited = '') => {
      if (node.type === 'text' && typeof node.value === 'string') {
        const styles = inherited
          .split(' ')
          .map((name) => tokenStyles[name])
          .filter(Boolean);
        tokens.push({
          kind: [inherited, ...styles].filter(Boolean).join(' ') || 'plain',
          text: node.value,
        });
      } else if (node.children) {
        const classes = node.properties?.className;
        const own = Array.isArray(classes)
          ? classes
              .filter(
                (value): value is string =>
                  typeof value === 'string' && /^hljs-[a-z0-9_-]+$/.test(value),
              )
              .join(' ')
          : '';
        for (const child of node.children) visit(child, [inherited, own].filter(Boolean).join(' '));
      }
    };
    visit(grammar.highlight(language, code));
    return tokens.map((token) => token.text).join('') === code ? tokens : plain;
  } catch {
    return plain;
  }
}

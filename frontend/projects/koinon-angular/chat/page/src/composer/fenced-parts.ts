// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
export type FencedPart =
  { kind: 'prose'; text: string } | { kind: 'code'; language: string; text: string };

export function fencedParts(text: string): FencedPart[] {
  const parts: FencedPart[] = [];
  const lineEnd = (start: number) => {
    const end = text.indexOf('\n', start);
    return end < 0 ? text.length : end + 1;
  };
  let cursor = 0,
    prose = 0;
  while (cursor < text.length) {
    const end = lineEnd(cursor);
    const opening = /^ {0,3}(`{3,}|~{3,})([^\r\n]*)\r?\n?$/.exec(text.slice(cursor, end));
    if (!opening || (opening[1][0] === '`' && opening[2].includes('`'))) {
      cursor = end;
      continue;
    }
    if (cursor > prose) parts.push({ kind: 'prose', text: text.slice(prose, cursor) });
    const codeStart = end;
    cursor = end;
    let codeEnd = text.length;
    while (cursor < text.length) {
      const next = lineEnd(cursor);
      const closing = /^ {0,3}(`{3,}|~{3,})[\t ]*\r?\n?$/.exec(text.slice(cursor, next));
      if (closing && closing[1][0] === opening[1][0] && closing[1].length >= opening[1].length) {
        codeEnd = cursor;
        cursor = next;
        break;
      }
      cursor = next;
    }
    parts.push({
      kind: 'code',
      language: opening[2].trim().split(/\s+/, 1)[0] || 'plaintext',
      text: text.slice(codeStart, codeEnd),
    });
    prose = cursor;
  }
  if (prose < text.length || !parts.length) parts.push({ kind: 'prose', text: text.slice(prose) });
  return parts;
}

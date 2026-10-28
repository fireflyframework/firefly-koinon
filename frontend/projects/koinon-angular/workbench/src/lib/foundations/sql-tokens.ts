// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
export interface SqlToken {
  kind: 'plain' | 'keyword' | 'string' | 'comment' | 'number' | 'identifier' | 'parameter';
  text: string;
}
const keywords = new Set(
  'SELECT FROM WHERE JOIN INNER LEFT RIGHT FULL OUTER CROSS NATURAL ON USING AS WITH RECURSIVE UNION ALL DISTINCT INTERSECT EXCEPT GROUP BY HAVING ORDER ASC DESC NULLS FIRST LAST LIMIT OFFSET FETCH ROW ROWS ONLY OVER PARTITION WINDOW QUALIFY FILTER CASE WHEN THEN ELSE END AND OR NOT IN IS NULL TRUE FALSE UNKNOWN LIKE ILIKE BETWEEN EXISTS ANY SOME CAST TRY_CAST DATE TIMESTAMP INTERVAL CURRENT_DATE CURRENT_TIMESTAMP COUNT SUM AVG MIN MAX COALESCE NULLIF ROW_NUMBER RANK DENSE_RANK LAG LEAD EXPLAIN ANALYZE DESCRIBE SHOW INSERT INTO VALUES UPDATE SET DELETE RETURNING CREATE ALTER DROP TABLE VIEW SCHEMA DATABASE MATERIALIZED MERGE MATCHED TRUNCATE UNNEST LATERAL'.split(
    ' ',
  ),
);

export function sqlTokens(source: string): readonly SqlToken[] {
  if (source.length > 131072) return [{ kind: 'plain', text: source }];
  const tokens: SqlToken[] = [];
  let index = 0;
  while (index < source.length) {
    const start = index,
      char = source[index],
      next = source[index + 1];
    let kind: SqlToken['kind'] = 'plain';
    if (char === '-' && next === '-') {
      kind = 'comment';
      index += 2;
      while (index < source.length && source[index] !== '\n') ++index;
    } else if (char === '/' && next === '*') {
      kind = 'comment';
      index += 2;
      let depth = 1;
      while (index < source.length && depth) {
        if (source.startsWith('/*', index)) {
          ++depth;
          index += 2;
        } else if (source.startsWith('*/', index)) {
          --depth;
          index += 2;
        } else ++index;
      }
    } else if (char === "'" || char === '"' || char === '`' || char === '[') {
      kind = char === "'" ? 'string' : 'identifier';
      const close = char === '[' ? ']' : char;
      ++index;
      while (index < source.length) {
        if (source[index] === '\\' && char === "'") {
          index = Math.min(source.length, index + 2);
          continue;
        }
        if (source[index++] === close) {
          if (source[index] === close) ++index;
          else break;
        }
      }
    } else if (char === '$') {
      const delimiter = /^\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$/.exec(source.slice(index))?.[0];
      if (delimiter) {
        kind = 'string';
        const close = source.indexOf(delimiter, index + delimiter.length);
        index = close < 0 ? source.length : close + delimiter.length;
      } else {
        kind = 'parameter';
        ++index;
        while (/\d/.test(source[index] ?? '')) ++index;
      }
    } else if (
      char === '?' ||
      (char === ':' && next !== ':' && /[A-Za-z_]/.test(next ?? '') && source[index - 1] !== ':')
    ) {
      kind = 'parameter';
      ++index;
      while (/[A-Za-z0-9_]/.test(source[index] ?? '')) ++index;
    } else if (/\d/.test(char)) {
      const number = /^(?:0[xX][0-9a-fA-F]+|\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/.exec(
        source.slice(index),
      )![0];
      kind = 'number';
      index += number.length;
    } else if (/[\p{L}_]/u.test(char)) {
      ++index;
      while (/[\p{L}\p{N}_$]/u.test(source[index] ?? '')) ++index;
      if (keywords.has(source.slice(start, index).toUpperCase())) kind = 'keyword';
    } else {
      ++index;
    }
    const text = source.slice(start, index),
      previous = tokens.at(-1);
    if (previous?.kind === kind) previous.text += text;
    else tokens.push({ kind, text });
    if (tokens.length > 8192) return [{ kind: 'plain', text: source }];
  }
  return tokens;
}

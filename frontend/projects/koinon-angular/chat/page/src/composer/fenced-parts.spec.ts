// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { fencedParts } from './fenced-parts';

it('separates backtick and tilde blocks while retaining exact multiline contents', () => {
  expect(fencedParts('Before\n```python\ndef greet():\n    return 1\n```\nAfter')).toEqual([
    { kind: 'prose', text: 'Before\n' },
    { kind: 'code', language: 'python', text: 'def greet():\n    return 1\n' },
    { kind: 'prose', text: 'After' },
  ]);
  expect(fencedParts('~~~json\r\n{"ok":true}\r\n~~~~\r\n')).toEqual([
    { kind: 'code', language: 'json', text: '{"ok":true}\r\n' },
  ]);
});
it('handles streaming open fences and plain code without stripping or guessing source', () => {
  expect(fencedParts('```\na\n\tb')).toEqual([
    { kind: 'code', language: 'plaintext', text: 'a\n\tb' },
  ]);
  expect(fencedParts('```unknown\n<svg onload="alert(1)">')).toEqual([
    { kind: 'code', language: 'unknown', text: '<svg onload="alert(1)">' },
  ]);
});
it('requires matching closing fences of sufficient length and keeps inline notation as prose', () => {
  expect(fencedParts('````js\na\n```\nb\n~~~~\n````')).toEqual([
    { kind: 'code', language: 'js', text: 'a\n```\nb\n~~~~\n' },
  ]);
  for (const text of [
    'inline `code` and ```js``` stay inline',
    '    ```not-a-fence\nx',
    '```bad`info\nx',
  ])
    expect(fencedParts(text)).toEqual([{ kind: 'prose', text }]);
});

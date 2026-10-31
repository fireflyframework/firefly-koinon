// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { codeTokens } from './code-tokens';

it('highlights explicit common languages without changing whitespace or untrusted markup', async () => {
  for (const [language, code] of [
    ['python', 'def greet(name):\n    return "<img src=x onerror=alert(1)>"\n'],
    ['json', '{"name": "你好", "enabled": true}\n'],
    ['javascript', '// comment\nconst answer = 42;\n'],
    ['php', '<?php\nfunction greet($name) { return "Hello"; }\n'],
  ]) {
    const tokens = await codeTokens(code, language);
    expect(tokens.map((token) => token.text).join('')).toBe(code);
    expect(tokens.some((token) => token.kind.startsWith('hljs-'))).toBe(true);
  }
});
it('keeps unknown, plain and oversized code exact without guessing a language', async () => {
  for (const language of ['unknown-language', 'plaintext', '']) {
    const code = '<script>alert(1)</script>\r\n\t &amp;';
    expect(await codeTokens(code, language)).toEqual([{ kind: 'plain', text: code }]);
  }
  const code = 'x'.repeat(131073);
  expect(await codeTokens(code, 'python')).toEqual([{ kind: 'plain', text: code }]);
});

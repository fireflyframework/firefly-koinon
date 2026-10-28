// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonCodeBlock } from './code-block';
import { sqlTokens } from '../foundations/sql-tokens';
it('preserves the exact recorded SQL while highlighting comments, quoted names, literals and parameters', () => {
  const sql = `-- SELECT remains a comment\nSELECT "order", 'it''s <img src=x>', $$quoted SELECT$$, $1, :tenant, 1.5e-3 FROM "finance"."orders" /* outer /* nested */ done */ WHERE id = ?;`;
  const tokens = sqlTokens(sql);
  expect(tokens.map((token) => token.text).join('')).toBe(sql);
  expect(tokens.find((token) => token.text.startsWith('-- SELECT'))?.kind).toBe('comment');
  expect(tokens.find((token) => token.text.includes("it''s"))?.kind).toBe('string');
  expect(tokens.find((token) => token.text === 'SELECT')?.kind).toBe('keyword');
  expect(tokens.find((token) => token.text === '$1')?.kind).toBe('parameter');
});
it('renders untrusted SQL as text rather than HTML and keeps it selectable with the keyboard', () => {
  TestBed.configureTestingModule({ imports: [KoinonCodeBlock] });
  const fixture = TestBed.createComponent(KoinonCodeBlock);
  const sql = `SELECT '<img src=x onerror="alert(1)">', '&amp;', '你好' FROM source;\n`;
  fixture.componentRef.setInput('code', sql);
  fixture.detectChanges();
  const pre = fixture.nativeElement.querySelector('pre') as HTMLElement;
  expect(pre.textContent).toBe(sql);
  expect(pre.tabIndex).toBe(0);
  expect(fixture.nativeElement.querySelector('img,script')).toBeNull();
  expect(fixture.nativeElement.querySelector('.keyword')?.textContent).toBe('SELECT');
});
it('bounds token expansion for oversized records without silently changing their text', () => {
  const sql = 'SELECT 1;\n'.repeat(15000);
  expect(sqlTokens(sql)).toEqual([{ kind: 'plain', text: sql }]);
});

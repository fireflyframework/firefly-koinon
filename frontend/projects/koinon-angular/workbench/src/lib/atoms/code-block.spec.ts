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
it('renders untrusted SQL as text rather than HTML and keeps it selectable with the keyboard', async () => {
  TestBed.configureTestingModule({ imports: [KoinonCodeBlock] });
  const fixture = TestBed.createComponent(KoinonCodeBlock);
  const sql = `SELECT '<img src=x onerror="alert(1)">', '&amp;', '你好' FROM source;\n`;
  fixture.componentRef.setInput('code', sql);
  fixture.detectChanges();
  await fixture.whenStable();
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
it('renders lazy language tokens safely and copies the original multiline code', async () => {
  TestBed.configureTestingModule({ imports: [KoinonCodeBlock] });
  const fixture = TestBed.createComponent(KoinonCodeBlock);
  const code = 'def greet():\n    return "<img src=x onerror=alert(1)>"\n';
  fixture.componentRef.setInput('code', code);
  fixture.componentRef.setInput('language', 'python');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('pre').textContent).toBe(code);
  expect(fixture.nativeElement.querySelector('.hljs-keyword').textContent).toBe('def');
  expect(fixture.nativeElement.querySelector('img,script')).toBeNull();
  const navigator = fixture.nativeElement.ownerDocument.defaultView.navigator;
  const previous = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
  const writeText = vi.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
  try {
    fixture.nativeElement.querySelector('button').click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(writeText).toHaveBeenCalledExactlyOnceWith(code);
    expect(fixture.componentInstance.copied()).toBe(true);
    expect(fixture.nativeElement.querySelector('button').getAttribute('aria-label')).toBe(
      'Copy code',
    );
  } finally {
    if (previous) Object.defineProperty(navigator, 'clipboard', previous);
    else Reflect.deleteProperty(navigator, 'clipboard');
  }
});
it('retains default SQL labels and ignores stale async highlighting after a language change', async () => {
  TestBed.configureTestingModule({ imports: [KoinonCodeBlock] });
  const fixture = TestBed.createComponent(KoinonCodeBlock);
  fixture.componentRef.setInput('language', 'python');
  fixture.componentRef.setInput('code', 'def greet(): pass');
  fixture.componentRef.setInput('language', 'sql');
  fixture.componentRef.setInput('code', 'SELECT 1;\n');
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('pre').textContent).toBe('SELECT 1;\n');
  expect(fixture.nativeElement.querySelector('.keyword').textContent).toBe('SELECT');
  expect(fixture.nativeElement.querySelector('button').getAttribute('aria-label')).toBe('Copy SQL');
});
it.each([['B'], ['B', 'A']])(
  'does not report an obsolete clipboard completion after code changes through %j',
  async (...changes) => {
    TestBed.configureTestingModule({ imports: [KoinonCodeBlock] });
    const fixture = TestBed.createComponent(KoinonCodeBlock);
    fixture.componentRef.setInput('code', 'A');
    const navigator = fixture.nativeElement.ownerDocument.defaultView.navigator;
    const previous = Object.getOwnPropertyDescriptor(navigator, 'clipboard');
    let complete!: () => void;
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: () =>
          new Promise<void>((resolve) => {
            complete = resolve;
          }),
      },
    });
    try {
      fixture.componentInstance.copy();
      for (const code of changes) fixture.componentRef.setInput('code', code);
      complete();
      await fixture.whenStable();
      expect(fixture.componentInstance.copied()).toBe(false);
    } finally {
      if (previous) Object.defineProperty(navigator, 'clipboard', previous);
      else Reflect.deleteProperty(navigator, 'clipboard');
    }
  },
);

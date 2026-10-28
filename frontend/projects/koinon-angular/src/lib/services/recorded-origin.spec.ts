// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonRecordedOrigin } from '../../../chat/page/src/artifacts/recorded-origin';
it('states unknown historical origin without substituting a current connection', () => {
  TestBed.configureTestingModule({ imports: [KoinonRecordedOrigin] });
  const fixture = TestBed.createComponent(KoinonRecordedOrigin);
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Original source identity was not recorded.');
  expect(fixture.nativeElement.querySelector('dl')).toBeNull();
});
it('renders explicit recorded origin fields as text without filling the layout with empty rows', () => {
  TestBed.configureTestingModule({ imports: [KoinonRecordedOrigin] });
  const fixture = TestBed.createComponent(KoinonRecordedOrigin);
  fixture.componentRef.setInput('origin', {
    original_filename: '<img src=x>.pdf',
    database: 'recorded-origin-db',
    url: 'https://example.invalid/private',
    password: 'must-not-render',
    dsn: 'must-not-render-dsn',
  });
  fixture.detectChanges();
  const text = fixture.nativeElement.textContent as string;
  expect(text).toContain('<img src=x>.pdf');
  expect(text).toContain('recorded-origin-db');
  expect(text).not.toContain('Not recorded');
  expect(fixture.nativeElement.querySelectorAll('dt').length).toBe(2);
  expect(text).not.toContain('example.invalid');
  expect(text).not.toContain('must-not-render');
  expect(fixture.nativeElement.querySelector('img,a,script')).toBeNull();
});
it('keeps the recorded original database, schema, table and file independent', () => {
  TestBed.configureTestingModule({ imports: [KoinonRecordedOrigin] });
  const fixture = TestBed.createComponent(KoinonRecordedOrigin);
  fixture.componentRef.setInput('origin', {
    original_filename: 'orders.xlsx',
    sheet_or_json_path: 'Sheet2',
    connection_name: 'Historical connection',
    connection_id: 'recorded-connection',
    database: 'origin-database',
    schema: 'origin-schema',
    table: 'origin-table',
  });
  fixture.detectChanges();
  for (const value of [
    'orders.xlsx',
    'Sheet2',
    'Historical connection',
    'origin-database',
    'origin-schema',
    'origin-table',
  ])
    expect(fixture.nativeElement.textContent).toContain(value);
  expect(fixture.nativeElement.textContent).not.toContain('recorded-connection');
});

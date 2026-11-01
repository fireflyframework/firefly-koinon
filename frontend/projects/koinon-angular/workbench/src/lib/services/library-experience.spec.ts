// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { KoinonLibraryTemplate } from '../templates/library-template';
import { KoinonPagination } from '../molecules/pagination';
import { KoinonI18n } from '../foundations/i18n';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
const item: CatalogEntry = {
  id: 'policy',
  name: 'Policy.pdf',
  kind: 'document',
  tenant_id: 'north',
  parent_id: 'source',
  workspace_id: 'space',
  project_id: 'project',
  description: 'Approved operating policy',
  metadata: {},
  status: 'ready',
  created_at: '2026-10-27T10:00:00Z',
};
function setup() {
  const fixture = TestBed.createComponent(KoinonLibraryTemplate);
  fixture.componentRef.setInput('serverControls', true);
  fixture.componentRef.setInput('items', [item]);
  fixture.componentRef.setInput('allowedKinds', [
    { value: 'document', label: 'Document' },
    { value: 'dataset', label: 'Dataset' },
  ]);
  fixture.componentRef.setInput('filter', {
    sort: 'name',
    order: 'asc',
    q: 'Policy',
    kind: 'document',
  });
  fixture.detectChanges();
  return fixture;
}
it('sorts the entire library through accessible column headers and resets the page', () => {
  const fixture = setup();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  const header = fixture.nativeElement.querySelector(
    '[role="columnheader"][aria-sort="ascending"]',
  );
  expect(header).not.toBeNull();
  header.querySelector('button').click();
  expect(changes).toEqual([{ sort: 'name', order: 'desc', page: 1 }]);
});
it('clears all active collection filters together without changing sort or scope', () => {
  const fixture = setup();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  const clear = Array.from(fixture.nativeElement.querySelectorAll('button')).find(
    (button) => (button as HTMLButtonElement).textContent?.trim() === 'Clear filters',
  ) as HTMLButtonElement;
  expect(clear).toBeDefined();
  clear.click();
  expect(changes).toEqual([
    { q: '', kind: undefined, status: undefined, tag: undefined, format: undefined, page: 1 },
  ]);
});
it('disables the page-size control while a request is loading', () => {
  const fixture = TestBed.createComponent(KoinonPagination);
  fixture.componentRef.setInput('page', {
    items: [item],
    total: 43,
    page: 1,
    page_size: 25,
    pages: 2,
  });
  fixture.componentRef.setInput('loading', true);
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('select').disabled).toBe(true);
});
it('shows recorded counts and derived tags while preserving unknown values', () => {
  const fixture = setup();
  fixture.componentRef.setInput('pageInfo', {
    items: [item],
    summaries: {
      policy: {
        child_count: null,
        document_count: null,
        dataset_count: null,
        table_count: null,
        row_count: null,
        column_count: null,
        page_count: 12,
        size_bytes: 2048,
        format: 'pdf',
        language: 'en',
        tags: ['pdf', 'en', 'policy'],
      },
    },
  });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('12 pages');
  expect(fixture.nativeElement.textContent).toContain('2 KB');
  expect(fixture.nativeElement.textContent).toContain('policy');
  expect(fixture.nativeElement.textContent).not.toContain('0 rows');
});
it('preserves recorded zero counts and hides missing statistics rather than inventing them', () => {
  const fixture = setup();
  fixture.componentRef.setInput('items', [{ ...item, kind: 'dataset' }]);
  fixture.componentRef.setInput('pageInfo', {
    items: [],
    summaries: {
      policy: {
        child_count: null,
        document_count: null,
        dataset_count: null,
        table_count: 1,
        row_count: 0,
        column_count: null,
        page_count: null,
        size_bytes: null,
        format: null,
        language: null,
        tags: [],
      },
    },
  });
  fixture.detectChanges();
  const text = fixture.nativeElement.textContent;
  expect(text).toContain('1 table, 0 rows');
  expect(text).not.toContain('0 columns');
  expect(text).not.toContain('0 B');
});
it('applies exact metadata filters through the server contract with normalization', () => {
  const fixture = setup();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  fixture.componentInstance.formatFilter = ' PDF ';
  fixture.componentInstance.tagFilter = ' Policy ';
  fixture.componentInstance.statusFilter = 'ready';
  fixture.nativeElement
    .querySelector('.filter-options form')
    .dispatchEvent(new Event('submit', { cancelable: true }));
  expect(changes).toEqual([{ status: 'ready', format: 'pdf', tag: 'policy', page: 1 }]);
});
it('renders metadata tags as text and emits a collection-wide tag filter without writes', () => {
  const fixture = setup();
  fixture.componentRef.setInput('pageInfo', {
    items: [item],
    summaries: { policy: { tags: ['<img src=x onerror=alert(1)>'] } },
  });
  fixture.detectChanges();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  fixture.nativeElement.querySelector('button.tag').click();
  expect(fixture.nativeElement.querySelector('img')).toBeNull();
  expect(changes).toEqual([{ tag: '<img src=x onerror=alert(1)>', page: 1 }]);
});
it('uses singular pagination copy for one item and omits empty pagination', () => {
  const fixture = TestBed.createComponent(KoinonPagination);
  fixture.componentRef.setInput('page', {
    items: [item],
    total: 1,
    page: 1,
    page_size: 25,
    pages: 1,
  });
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.range').textContent.trim()).toBe('1–1 of 1 item');
  fixture.componentRef.setInput('page', { items: [], total: 0, page: 1, page_size: 25, pages: 0 });
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('nav')).toBeNull();
});
it('keeps sorting by date added available in the contextual desktop controls', async () => {
  const fixture = setup();
  await fixture.whenStable();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  const select = fixture.nativeElement.querySelector(
    '.filter-options select[name="sort"]',
  ) as HTMLSelectElement;
  expect(select).not.toBeNull();
  select.value = 'created_at.desc';
  select.dispatchEvent(new Event('change'));
  fixture.nativeElement
    .querySelector('.filter-options form')
    .dispatchEvent(new Event('submit', { cancelable: true }));
  expect(changes).toEqual([
    {
      sort: 'created_at',
      order: 'desc',
      status: undefined,
      format: undefined,
      tag: undefined,
      page: 1,
    },
  ]);
});
it('toggles the displayed default name order when the host omits an explicit filter', () => {
  const fixture = setup();
  fixture.componentRef.setInput('filter', {});
  fixture.detectChanges();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  fixture.nativeElement
    .querySelector('[role="columnheader"][aria-sort="ascending"] button')
    .click();
  expect(changes).toEqual([{ sort: 'name', order: 'desc', page: 1 }]);
});
it('preserves a draft sort when a pending filter update arrives without changing the active order', () => {
  const fixture = setup();
  fixture.componentInstance.metadataSort = 'created_at.desc';
  fixture.componentRef.setInput('filter', { sort: 'name', order: 'asc', format: 'pdf' });
  fixture.detectChanges();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  fixture.nativeElement
    .querySelector('.filter-options form')
    .dispatchEvent(new Event('submit', { cancelable: true }));
  expect(changes).toEqual([
    {
      sort: 'created_at',
      order: 'desc',
      status: undefined,
      format: 'pdf',
      tag: undefined,
      page: 1,
    },
  ]);
});
it('omits a secondary name line when no description was recorded', () => {
  const fixture = setup();
  fixture.componentRef.setInput('items', [{ ...item, description: '' }]);
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.name-wrap .description')).toBeNull();
});
it('clarifies that contents are sorted by type', () => {
  const fixture = setup();
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  const header = Array.from(fixture.nativeElement.querySelectorAll('[role="columnheader"]')).find(
    (node) => (node as HTMLElement).textContent?.includes('Type & contents'),
  ) as HTMLElement;
  expect(header).toBeDefined();
  header.querySelector('button')!.click();
  expect(changes).toEqual([{ sort: 'kind', order: 'asc', page: 1 }]);
});
it('presents recorded format and language tags clearly while preserving raw filters and custom case', () => {
  const fixture = setup();
  fixture.componentRef.setInput('pageInfo', {
    items: [item],
    summaries: { policy: { format: 'pdf', language: 'en', tags: ['pdf', 'en', 'PII', 'Finance'] } },
  });
  fixture.detectChanges();
  const labels = Array.from(fixture.nativeElement.querySelectorAll('.tag')).map((node) =>
    (node as HTMLElement).textContent?.trim(),
  );
  expect(labels).toContain('PDF');
  expect(labels).toContain('English');
  expect(labels).toContain('PII');
  const changes: unknown[] = [];
  fixture.componentInstance.filterChanged.subscribe((value) => changes.push(value));
  (fixture.nativeElement.querySelector('button.tag') as HTMLButtonElement).click();
  expect(changes).toEqual([{ tag: 'pdf', page: 1 }]);
});
it('marks generic introductory copy so the mobile heading can stay compact', () => {
  const fixture = setup();
  fixture.componentRef.setInput('descriptionIsGeneric', true);
  fixture.componentRef.setInput('canAdd', true);
  fixture.detectChanges();
  expect(
    fixture.nativeElement.querySelector('.library-heading p.generic-description'),
  ).not.toBeNull();
  expect(
    fixture.nativeElement.querySelector('.library-add [aria-label="Add knowledge"]'),
  ).not.toBeNull();
});

it('localizes recorded language names when the interface locale changes and leaves unknown labels intact', () => {
  const fixture = setup();
  fixture.componentRef.setInput('pageInfo', {
    items: [item],
    summaries: { policy: { language: 'es', tags: ['es', 'PII', 'Finance'] } },
  });
  TestBed.inject(KoinonI18n).apply({ locale: 'es-MX', time_zone: 'UTC', response_language: 'es' });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('Español');
  expect(fixture.nativeElement.textContent).toContain('Finance');
  fixture.componentRef.setInput('pageInfo', {
    items: [item],
    summaries: { policy: { language: 'not a language code', tags: ['not a language code'] } },
  });
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('not a language code');
});

it('keeps contextual creation and knowledge upload as distinct authorized actions', () => {
  const fixture = setup();
  fixture.componentRef.setInput('canAdd', true);
  fixture.componentRef.setInput('createLabel', 'Create a space');
  fixture.detectChanges();
  const created = vi.fn(), uploaded = vi.fn();
  fixture.componentInstance.createRequested.subscribe(created);
  fixture.componentInstance.addRequested.subscribe(uploaded);
  const buttons = [...fixture.nativeElement.querySelectorAll('button')] as HTMLButtonElement[];
  buttons.find(button => button.textContent?.trim() === 'Create a space')!.click();
  expect(created).toHaveBeenCalledOnce();
  expect(uploaded).not.toHaveBeenCalled();
  buttons.find(button => button.getAttribute('aria-label') === 'Add knowledge')!.click();
  expect(uploaded).toHaveBeenCalledOnce();
  fixture.componentRef.setInput('canAdd', false);
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('.library-actions')).toBeNull();
});

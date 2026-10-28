// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import {
  KoinonClient,
  type CatalogEntry,
  type KoinonTransport,
  type RequestOptions,
} from '@fireflyframework/koinon-sdk';
import { KoinonFacade } from '../koinon-facade';
import { KoinonClientContext } from '../services/client-context';
import { KoinonCommandPalette } from './command-palette';
function setup(
  request: KoinonTransport['request'] = async <T>() =>
    ({ items: [], page: 1, pages: 0, total: 0 }) as T,
) {
  const facade = {
    tenantId: signal('north'),
    workspaceId: signal('space'),
    projectId: signal(''),
    permissions: signal(new Set(['catalog:read'])),
    authRequired: signal(false),
    context: signal({ subject: 'issuer|admin', tenants: [], workspaces: [] }),
    entries: signal([]),
  };
  const transport: KoinonTransport = {
    request,
    stream: () => {
      throw Error('Unexpected stream');
    },
  };
  TestBed.configureTestingModule({
    imports: [KoinonCommandPalette],
    providers: [
      { provide: KoinonFacade, useValue: facade },
      {
        provide: KoinonClientContext,
        useValue: { get: () => new KoinonClient({ transport }), revision: signal(0) },
      },
    ],
  });
  const fixture = TestBed.createComponent(KoinonCommandPalette);
  fixture.componentRef.setInput('commands', [
    { id: 'blocked', title: 'Forbidden action', disabled: true },
    { id: 'upload', title: 'Upload files', description: 'Add to this space', icon: 'upload' },
    { id: 'new-chat', title: 'New chat', icon: 'chat' },
  ]);
  fixture.componentRef.setInput('open', true);
  fixture.detectChanges();
  return { fixture, palette: fixture.componentInstance, facade };
}
const key = (dialog: HTMLDialogElement, name: string) =>
  dialog.dispatchEvent(
    new KeyboardEvent('keydown', { key: name, bubbles: true, cancelable: true }),
  );
const type = (input: HTMLInputElement, value: string) => {
  input.value = value;
  input.dispatchEvent(new Event('input', { bubbles: true }));
};
afterEach(() => vi.useRealTimers());
it('labels the modal combobox, focuses input and restores the exact invoking element on Escape', async () => {
  const trigger = document.createElement('button');
  document.body.append(trigger);
  trigger.focus();
  const { fixture, palette } = setup();
  const closed = vi.fn();
  palette.closed.subscribe(closed);
  await Promise.resolve();
  fixture.detectChanges();
  const dialog: HTMLDialogElement = fixture.nativeElement.querySelector('dialog'),
    input: HTMLInputElement = fixture.nativeElement.querySelector('input');
  expect(dialog.open).toBe(true);
  expect(dialog.getAttribute('aria-labelledby')).toBeTruthy();
  expect(input.getAttribute('role')).toBe('combobox');
  expect(input.getAttribute('aria-controls')).toBeTruthy();
  expect(document.activeElement).toBe(input);
  key(dialog, 'Escape');
  expect(closed).toHaveBeenCalledOnce();
  expect(dialog.open).toBe(false);
  expect(document.activeElement).toBe(trigger);
  fixture.destroy();
  trigger.remove();
});
it('navigates enabled options with arrows/Home/End and emits only a currently allowed command', () => {
  const { fixture, palette } = setup();
  const selected = vi.fn();
  palette.commandSelected.subscribe(selected);
  const dialog: HTMLDialogElement = fixture.nativeElement.querySelector('dialog');
  key(dialog, 'Home');
  key(dialog, 'ArrowDown');
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelector('[aria-selected="true"]').textContent).toContain(
    'New chat',
  );
  key(dialog, 'ArrowUp');
  key(dialog, 'End');
  key(dialog, 'Enter');
  expect(selected).toHaveBeenCalledExactlyOnceWith('new-chat');
});
it('filters command names/descriptions and refuses a command revoked after it was rendered', () => {
  const { fixture, palette } = setup();
  const selected = vi.fn();
  palette.commandSelected.subscribe(selected);
  const stale = palette
    .options()
    .find((option) => option.kind === 'command' && option.command.id === 'upload')!;
  fixture.componentRef.setInput('commands', [
    { id: 'upload', title: 'Upload files', disabled: true },
  ]);
  fixture.detectChanges();
  palette.choose(stale);
  expect(selected).not.toHaveBeenCalled();
  type(fixture.nativeElement.querySelector('input'), 'absent');
  fixture.detectChanges();
  expect(fixture.nativeElement.querySelectorAll('[data-kind="command"]')).toHaveLength(0);
});
it('selects real catalog entries, uses server pagination and fences a stale resource click', async () => {
  vi.useFakeTimers();
  const pages: number[] = [];
  const resource: CatalogEntry = {
    id: 'policy',
    name: 'Policy.pdf',
    kind: 'document',
    tenant_id: 'north',
    workspace_id: 'space',
    project_id: 'project',
    parent_id: 'source',
    description: 'Approved policy',
    status: 'ready',
    metadata: {},
    created_at: '2026-10-27',
  };
  const { fixture, palette, facade } = setup(
    async <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      const page = Number(options!.query!['page']);
      pages.push(page);
      return { items: [resource], page, page_size: 8, pages: 3, total: 19 } as T;
    },
  );
  const chosen = vi.fn();
  palette.resourceSelected.subscribe(chosen);
  type(fixture.nativeElement.querySelector('input'), 'policy');
  fixture.detectChanges();
  await vi.advanceTimersByTimeAsync(250);
  fixture.detectChanges();
  const stale = palette.options().find((option) => option.kind === 'resource')!;
  expect(stale).toBeDefined();
  expect(fixture.nativeElement.textContent).toContain('19');
  (fixture.nativeElement.querySelector('[data-page="next"]') as HTMLButtonElement).click();
  await Promise.resolve();
  fixture.detectChanges();
  expect(pages).toEqual([1, 2]);
  facade.context.set({ ...facade.context(), subject: 'issuer|other' });
  palette.choose(stale);
  expect(chosen).not.toHaveBeenCalled();
});
it('emits an explicit full-search intent without running any model or navigating by itself', () => {
  const { fixture, palette } = setup();
  const search = vi.fn(),
    closed = vi.fn();
  palette.searchRequested.subscribe(search);
  palette.closed.subscribe(closed);
  type(fixture.nativeElement.querySelector('input'), '  renewal threshold  ');
  fixture.detectChanges();
  (fixture.nativeElement.querySelector('[data-kind="search"]') as HTMLButtonElement).click();
  expect(search).toHaveBeenCalledExactlyOnceWith('renewal threshold');
  expect(closed).toHaveBeenCalledOnce();
});
it('never exposes catalog rows while closed or after destroying an outstanding search', async () => {
  vi.useFakeTimers();
  let resolve!: (value: unknown) => void;
  let aborted!: AbortSignal;
  const { fixture, palette } = setup(
    <T>(_method: unknown, _path: string, options?: RequestOptions) => {
      aborted = options!.signal!;
      return new Promise<T>((complete) => {
        resolve = complete as (value: unknown) => void;
      });
    },
  );
  type(fixture.nativeElement.querySelector('input'), 'policy');
  fixture.detectChanges();
  await vi.advanceTimersByTimeAsync(250);
  fixture.componentRef.setInput('open', false);
  fixture.detectChanges();
  expect(aborted.aborted).toBe(true);
  expect(palette.search.page().items).toEqual([]);
  fixture.destroy();
  resolve({ items: [], total: 99 });
  await Promise.resolve();
});

it('keeps an observed empty page honest without displaying page1 of0', async () => {
  vi.useFakeTimers();
  const { fixture } = setup();
  type(fixture.nativeElement.querySelector('input'), 'absent');
  fixture.detectChanges();
  await vi.advanceTimersByTimeAsync(250);
  fixture.detectChanges();
  expect(fixture.nativeElement.textContent).toContain('No matching resources.');
  expect(fixture.nativeElement.querySelector('nav')).toBeNull();
  expect(fixture.nativeElement.querySelector('[data-kind="search"]')).toBeTruthy();
});

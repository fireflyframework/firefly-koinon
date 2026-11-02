// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import type { CatalogEntry } from '@fireflyframework/koinon-sdk';
import { KoinonDocumentViewerPanel } from './document-viewer';
import { KoinonDocumentViewer } from '../services/document-viewer';
import { KoinonI18n } from '../foundations/i18n';
function setup(locale = 'en-US') {
  const entry = { id: 'doc', name: 'A very long policy document.pdf' } as CatalogEntry;
  const state = {
    target: signal(entry),
    open: vi.fn(),
    close: vi.fn(),
    version: signal({
      source_version_id: 'serving',
      sha256: 'a'.repeat(64),
      created_at: '2026-11-01T10:00:00Z',
    }),
    parts: signal({ items: [], pages: 0 }),
    content: signal({ text: '<img src=x onerror=alert(1)> — política', extraction_id: 'view' }),
    preview: signal(null),
    pending: signal(false),
    error: signal(''),
    canPreview: signal(true),
    canDownload: () => !!state.version(),
    transferLimited: signal(false),
    downloadOriginal: vi.fn(),
    previewOriginal: vi.fn(),
    clearPreview: vi.fn(),
  };
  TestBed.overrideComponent(KoinonDocumentViewerPanel, {
    set: { providers: [{ provide: KoinonDocumentViewer, useValue: state }] },
  });
  const fixture = TestBed.createComponent(KoinonDocumentViewerPanel);
  fixture.componentRef.setInput('entry', entry);
  fixture.debugElement.injector
    .get(KoinonI18n)
    .apply({ locale, time_zone: 'UTC', response_language: locale.startsWith('es') ? 'es' : 'en' });
  fixture.detectChanges();
  return { fixture, state };
}
it('renders escaped source text and labels extraction separately from original download', () => {
  const { fixture, state } = setup();
  expect(fixture.nativeElement.querySelector('.document-text img')).toBeNull();
  expect(fixture.nativeElement.querySelector('.document-text').textContent).toContain(
    '<img src=x onerror=alert(1)>',
  );
  expect(fixture.nativeElement.textContent).toContain('not the original page layout');
  const button = [...fixture.nativeElement.querySelectorAll('button')].find((b) =>
    b.textContent.includes('Download original'),
  );
  button.click();
  expect(state.downloadOriginal).toHaveBeenCalledOnce();
  fixture.destroy();
});
it('uses Spanish reader and download labels without claiming Office layout rendering', () => {
  const { fixture } = setup('es-ES');
  expect(fixture.nativeElement.textContent).toContain('Texto extraído');
  expect(fixture.nativeElement.textContent).toContain('Descargar original');
  expect(fixture.nativeElement.textContent).toContain('no el diseño de página original');
  fixture.destroy();
});
it('disables downloads until a version is authorized and closes through the native focus panel', () => {
  const { fixture, state } = setup();
  state.version.set(null as never);
  fixture.detectChanges();
  const button = [...fixture.nativeElement.querySelectorAll('button')].find((b) =>
    b.textContent.includes('Download original'),
  );
  expect(button.disabled).toBe(true);
  const closed = vi.fn();
  fixture.componentInstance.closed.subscribe(closed);
  fixture.nativeElement.querySelector('button.close').click();
  expect(state.close).toHaveBeenCalledOnce();
  expect(closed).toHaveBeenCalledOnce();
  fixture.destroy();
});

it('offers a user-activated isolated PDF browser link without embedding untrusted content', () => {
  const { fixture, state } = setup();
  state.preview.set({ url: 'blob:controlled-pdf', type: 'application/pdf' } as never);
  fixture.detectChanges();
  const link = fixture.nativeElement.querySelector('a.pdf-open');
  expect(link.getAttribute('target')).toBe('_blank');
  expect(link.getAttribute('rel')).toBe('noopener noreferrer');
  expect(link.getAttribute('href')).toBe('blob:controlled-pdf');
  expect(fixture.nativeElement.querySelector('iframe')).toBeNull();
  fixture.destroy();
});

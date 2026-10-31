// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { DOCUMENT } from '@angular/common';
import { ElementRef, Injectable, OnDestroy, inject, signal } from '@angular/core';
interface FontEntry {
  face: FontFace;
  family: string;
  ready: Promise<FontFace>;
  references: number;
}
const documents = new WeakMap<Document, Map<string, FontEntry>>();
type InterfaceFont = 'Manrope' | 'Inter';
function acquire(document: Document, url: string, font: InterfaceFont) {
  let store = documents.get(document);
  if (!store) {
    store = new Map();
    documents.set(document, store);
  }
  const cache = store;
  let entry = cache.get(url);
  if (!entry) {
    const family = 'Koinon' + font + '-' + crypto.getRandomValues(new Uint32Array(4)).join('-');
    const face = new FontFace(family, 'url(' + JSON.stringify(url) + ') format("woff2")', {
      weight: font === 'Inter' ? '100 900' : '200 800',
      style: 'normal',
      display: 'swap',
    });
    entry = { face, family, ready: face.load(), references: 0 };
    cache.set(url, entry);
    const current = entry;
    void current.ready
      .then(() => {
        if (current.references > 0) document.fonts.add(current.face);
      })
      .catch(() => {
        if (cache.get(url) === current) cache.delete(url);
      });
  }
  entry.references++;
  const current = entry;
  let released = false;
  return {
    family: entry.family,
    ready: entry.ready,
    release() {
      if (released) return;
      released = true;
      if (--current.references === 0) {
        document.fonts.delete(current.face);
        if (cache.get(url) === current) cache.delete(url);
      }
    },
  };
}
@Injectable()
export class KoinonFontLoader implements OnDestroy {
  private readonly document = inject(DOCUMENT);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly original = this.host.style.getPropertyValue('--ffk-font');
  private handle?: ReturnType<typeof acquire>;
  private revision = 0;
  private asset = '';
  readonly state = signal<'idle' | 'loading' | 'loaded' | 'unavailable'>('idle');
  async load(brandBase: string, font: InterfaceFont = 'Manrope') {
    if (typeof FontFace === 'undefined' || !this.document.fonts)
      return this.state.set('unavailable');
    let url: URL;
    try {
      const base = new URL(brandBase.replace(/\/$/, '') + '/', this.document.baseURI);
      if (
        !['http:', 'https:'].includes(base.protocol) ||
        base.username ||
        base.password ||
        base.search ||
        base.hash ||
        !['Manrope', 'Inter'].includes(font)
      )
        throw new Error();
      url = new URL('fonts/' + font.toLowerCase() + '-latin-wght-normal.woff2', base);
    } catch {
      return this.state.set('unavailable');
    }
    if (this.asset === url.href && this.handle) return;
    this.asset = url.href;
    const revision = ++this.revision;
    this.handle?.release();
    this.restore();
    const handle = acquire(this.document, url.href, font);
    this.handle = handle;
    this.state.set('loading');
    try {
      await handle.ready;
      if (revision !== this.revision) return;
      this.host.style.setProperty('--ffk-font', '"' + handle.family + '", system-ui, sans-serif');
      this.state.set('loaded');
    } catch {
      if (revision !== this.revision) return;
      handle.release();
      this.handle = undefined;
      this.state.set('unavailable');
    }
  }
  private restore() {
    if (this.original) this.host.style.setProperty('--ffk-font', this.original);
    else this.host.style.removeProperty('--ffk-font');
  }
  ngOnDestroy() {
    ++this.revision;
    this.handle?.release();
    this.restore();
  }
}

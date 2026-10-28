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
function acquire(document: Document, url: string) {
  let store = documents.get(document);
  if (!store) {
    store = new Map();
    documents.set(document, store);
  }
  const cache = store;
  let entry = cache.get(url);
  if (!entry) {
    const identity = crypto.getRandomValues(new Uint32Array(4));
    const family = 'KoinonManrope-' + [...identity].map((value) => value.toString(16)).join('');
    const face = new FontFace(family, 'url(' + JSON.stringify(url) + ') format("woff2")', {
      weight: '200 800',
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
  async load(brandBase: string) {
    if (typeof FontFace === 'undefined' || !this.document.fonts) {
      this.state.set('unavailable');
      return;
    }
    let url: URL;
    try {
      const base = new URL(brandBase.replace(/\/$/, '') + '/', this.document.baseURI);
      if (
        !['http:', 'https:'].includes(base.protocol) ||
        base.username ||
        base.password ||
        base.search ||
        base.hash
      )
        throw new Error('Invalid brand asset base');
      url = new URL('fonts/manrope-latin-wght-normal.woff2', base);
    } catch {
      this.state.set('unavailable');
      return;
    }
    if (this.asset === url.href && this.handle) return;
    this.asset = url.href;
    const revision = ++this.revision;
    this.handle?.release();
    this.restore();
    const handle = acquire(this.document, url.href);
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

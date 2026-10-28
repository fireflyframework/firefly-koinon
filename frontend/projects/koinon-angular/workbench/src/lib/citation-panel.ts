// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {KoinonTextPipe} from './foundations/i18n';
import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy } from '@angular/core';
import type { Citation } from '@fireflyframework/koinon-sdk';
@Component({imports:[KoinonTextPipe],
  selector: 'ffk-citation-panel',
  template: `<article>
    <h3>{{ citation.title || 'Source evidence' }}</h3>
    @if (citation.text) {
      <blockquote>{{ citation.text }}</blockquote>
    }
    <dl>
      @if (citation.page) {
        <dt>{{"Page"|ffkText}}</dt>
        <dd>{{ citation.page }}</dd>
      }
      @if (citation.section) {
        <dt>{{"Section"|ffkText}}</dt>
        <dd>{{ citation.section }}</dd>
      }
      @if (citation.document_id || citation.asset_id) {
        <dt>{{"Resource reference"|ffkText}}</dt>
        <dd>{{ citation.asset_id || citation.document_id }}</dd>
      }
      @if (citation.chunk_id) {
        <dt>{{"Chunk"|ffkText}}</dt>
        <dd>{{ citation.chunk_id }}</dd>
      }
    </dl>
    <div>
      @if (citation.asset_id || citation.document_id) {
        <button
          type="button"
          (click)="resourceRequested.emit(citation.asset_id || citation.document_id!)"
        >
          {{"Show resource"|ffkText}}
        </button>
      }
      @if (safeUrl()) {
        <a [href]="safeUrl()" target="_blank" rel="noopener noreferrer">{{"Open original source"|ffkText}}</a>
      }
    </div>
  </article>`,
  styles: `
    :host {
      display: block;
    }
    h3 {
      font-size: 16px;
      font-weight: 600;
      margin: 0 0 15px;
    }
    blockquote {
      font-size: 14px;
      line-height: 1.9;
      padding: 4px 0 4px 17px;
      border-left: 2px solid var(--ffk-amber, #ffb34a);
      margin: 0 0 22px;
      white-space: pre-wrap;
    }
    dl {
      font-size: 11px;
    }
    dt {
      color: var(--muted, var(--ffk-muted, #62645b));
      margin-top: 12px;
    }
    dd {
      margin: 4px 0;
      overflow-wrap: anywhere;
    }
    article > div {
      display: flex;
      gap: 14px;
      align-items: center;
      margin-top: 22px;
    }
    button,
    a {
      font: inherit;
      font-size: 12px;
      border-radius: 5px;
      padding: 9px 12px;
      border: 1px solid var(--line, #d8d4ca);
      background: var(--surface, #fff);
      color: inherit;
      cursor: pointer;
    }
    a {
      text-decoration: none;
    }
    button:focus-visible,
    a:focus-visible {
      outline: 2px solid var(--ffk-gold, #855414);
      outline-offset: 3px;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonCitationPanel {
  @Input({ required: true }) citation!: Citation;
  @Output() resourceRequested = new EventEmitter<string>();
  safeUrl(): string | null {
    try {
      const url = new URL(this.citation.url ?? '');
      return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
    } catch {
      return null;
    }
  }
}

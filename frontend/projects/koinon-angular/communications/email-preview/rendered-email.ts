// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, ElementRef, Input, ViewChild } from '@angular/core';
import { KoinonTextPipe } from '@fireflyframework/koinon-angular';
@Component({
  selector: 'ffk-rendered-email',
  imports: [KoinonTextPipe],
  template: `<p>{{ 'Links are disabled in this email preview.' | ffkText }}</p>
    <iframe
      #frame
      sandbox=""
      referrerpolicy="no-referrer"
      [title]="'Rendered email preview' | ffkText"
    ></iframe>`,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    p {
      font-size: 12px;
      color: var(--ui-muted);
      line-height: 1.8;
    }
    iframe {
      display: block;
      width: 100%;
      height: 680px;
      border: 1px solid var(--ui-line);
      border-radius: 8px;
      background: #fff;
    }
    @media (max-width: 600px) {
      iframe {
        height: 780px;
      }
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonRenderedEmail {
  private html = '';
  private frame: HTMLIFrameElement | undefined;
  @ViewChild('frame') set target(value: ElementRef<HTMLIFrameElement> | undefined) {
    this.frame = value?.nativeElement;
    this.render();
  }
  @Input() set value(value: string) {
    this.html = value.length <= 131072 ? value : '';
    this.render();
  }
  private render() {
    if (!this.frame) return;
    const policy = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">`;
    const template = document.createElement('template');
    // Detached template content is inert. No preview node enters the host document.
    // Template parsing drops document containers; ordinary divs retain their typography and palette.
    template.innerHTML = this.html.replace(/(<\/?)(?:html|head|body)(?=[\s>])/gi, '$1div');
    template.content.querySelectorAll('a,area').forEach((link) => {
      link.removeAttribute('href');
      link.removeAttribute('xlink:href');
      link.removeAttribute('target');
    });
    template.content
      .querySelectorAll('meta[http-equiv],base,form,script,iframe,object,embed')
      .forEach((node) => node.remove());
    this.frame.srcdoc = policy + '<style>body{margin:0}</style>' + template.innerHTML;
  }
}

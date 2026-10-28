// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
@Component({
  selector: 'ffk-icon',
  template: `<svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path [attr.d]="paths[name] || paths['file']" />
  </svg>`,
  styles: `
    :host {
      display: inline-flex;
      width: 1.2em;
      height: 1.2em;
      flex: 0 0 auto;
    }
    svg {
      width: 100%;
      height: 100%;
    }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonIcon {
  @Input() name = 'file';
  readonly paths: Record<string, string> = {
    heart:
      'M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8',
    info: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20M12 11v6M12 7h.01',
    file: 'M14 3H6v18h14V9ZM14 3v6h6M8 13h8M8 17h5',
    grid: 'M3 3h7v7H3ZM14 3h7v7h-7ZM3 14h7v7H3ZM14 14h7v7h-7Z',
    table: 'M3 4h18v16H3ZM3 9h18M3 14h18M9 9v11M15 9v11',
    chart: 'M3 3v18h18M7 16v-5M12 16V7M17 16v-8',
    folder: 'M3 7V4h6l2 3h10v13H3Z',
    search: 'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
    chat: 'M21 15H8l-5 6V3h18ZM7 8h10M7 12h7',
    download: 'M12 3v13M7 11l5 5 5-5M3 17v4h18v-4',
    upload: 'M12 16V3M7 8l5-5 5 5M3 15v6h18v-6',
    jobs: 'M8 3h8v4H8ZM5 5H3v16h18V5h-2M7 12l2 2 4-4M7 18h10',
    lineage: 'M12 8v4M4 16v-4h16v4M9 2h6v6H9ZM1 16h6v6H1ZM17 16h6v6h-6Z',
    users:
      'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M22 21v-2a4 4 0 0 0-3-4M16 3a4 4 0 0 1 0 8',
    filter: 'M4 6h16M7 12h10M10 18h4',
    settings:
      'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1Z',
    code: 'M8 7l-5 5 5 5M16 7l5 5-5 5M14 3l-4 18',
    plus: 'M12 5v14M5 12h14',
    'arrow-up': 'M12 19V5M5 12l7-7 7 7',
    paperclip: 'm21 11-9 9a6 6 0 0 1-8-8L15 2a4 4 0 0 1 6 6L10 19a2 2 0 0 1-3-3L17 6',
    image: 'M3 3h18v18H3ZM3 17l6-6 4 4 3-3 5 5M15 7h.01',
    stop: 'M7 7h10v10H7Z',
    'chevron-left': 'M15 5l-7 7 7 7',
    chevron: 'M9 5l7 7-7 7',
    down: 'M5 9l7 7 7-7',
    close: 'M6 6l12 12M6 18L18 6',
    refresh: 'M20 7V2l-4 4M4 17v5l4-4M20 7a9 9 0 0 0-15-2M4 17a9 9 0 0 0 15 2',
    sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1',
    moon: 'M21 13a9 9 0 1 1-10-10 7 7 0 0 0 10 10',
    logout: 'M9 3H3v18h6M9 12h13M17 7l5 5-5 5',
    check: 'M5 12l4 4L20 5',
    alert: 'M12 9v4M12 17h.01M2 21 12 3l10 18Z',
    menu: 'M3 6h18M3 12h18M3 18h18',
    copy: 'M8 8h13v13H8ZM16 5V2H2v14h3',
    external: 'M14 3h7v7M21 3 10 14M10 3H3v18h18v-7',
    shield: 'M12 2l9 4v7c0 4-4 7-9 9-5-2-9-5-9-9V6ZM8 12l3 3 5-6',
    history: 'M3 3v5h5M3 8a9 9 0 1 1-1 7M12 7v5l3 2',
    spark: 'M12 2l2 7 7 3-7 2-2 8-3-8-7-2 7-3Z',
    link: 'M10 13a5 5 0 0 0 7 0l4-4a5 5 0 0 0-7-7l-2 2M14 11a5 5 0 0 0-7 0l-4 4a5 5 0 0 0 7 7l2-2',
  };
}

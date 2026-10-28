// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  Output,
  ViewChild,
} from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { KoinonIcon } from '../atoms/icon';
import { KoinonTextPipe } from '../foundations/i18n';
let nextPanel = 0;
@Component({
  selector: 'ffk-side-panel',
  imports: [CdkTrapFocus, KoinonIcon, KoinonTextPipe],
  template: `<dialog
    #panel
    tabindex="-1"
    [attr.aria-labelledby]="headingId"
    [attr.aria-describedby]="description ? descriptionId : null"
    (cancel)="cancel($event)"
    (click)="backdrop($event)"
    (keydown.escape)="cancel($event)"
    [cdkTrapFocus]="open"
  >
    <header>
      <div>
        <h2 #headingElement [id]="headingId" tabindex="-1">{{ heading }}</h2>
        @if (description) {
          <p [id]="descriptionId">{{ description }}</p>
        }
      </div>
      <button
        type="button"
        class="close"
        [attr.aria-label]="'Close details' | ffkText"
        (click)="dismiss()"
      >
        <ffk-icon name="close" />
      </button>
    </header>
    <div class="body"><ng-content /></div>
    <div class="panel-footer"><ng-content select="[panel-footer]" /></div>
  </dialog>`,
  styleUrl: './side-panel.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonSidePanel implements AfterViewInit, OnChanges, OnDestroy {
  @Input() open = false;
  @Input() heading = 'Details';
  @Input() description = '';
  @Output() closed = new EventEmitter<void>();
  @ViewChild('panel') private panel?: ElementRef<HTMLDialogElement>;
  @ViewChild('headingElement') private title?: ElementRef<HTMLElement>;
  readonly headingId = 'koinon-panel-heading-' + ++nextPanel;
  readonly descriptionId = this.headingId + '-description';
  private previous: HTMLElement | null = null;
  ngAfterViewInit() {
    this.sync();
  }
  ngOnChanges() {
    this.sync();
  }
  private sync() {
    const panel = this.panel?.nativeElement;
    if (!panel) return;
    if (this.open && !panel.open) {
      this.previous = (panel.getRootNode() as Document | ShadowRoot)
        .activeElement as HTMLElement | null;
      if (typeof panel.showModal === 'function') panel.showModal();
      else panel.setAttribute('open', '');
      queueMicrotask(() => {
        if (this.open && panel.open) this.title?.nativeElement.focus({ preventScroll: true });
      });
    } else if (!this.open && panel.open) this.close();
  }
  private close() {
    const panel = this.panel?.nativeElement;
    if (!panel) return;
    if (typeof panel.close === 'function') panel.close();
    else panel.removeAttribute('open');
    if (this.previous?.isConnected) this.previous.focus({ preventScroll: true });
    this.previous = null;
  }
  dismiss() {
    this.close();
    this.closed.emit();
  }
  cancel(event: Event) {
    event.preventDefault();
    event.stopPropagation();
    this.dismiss();
  }
  backdrop(event: MouseEvent) {
    const panel = this.panel?.nativeElement;
    if (event.target !== panel || !panel) return;
    const r = panel.getBoundingClientRect();
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      this.dismiss();
  }
  ngOnDestroy() {
    this.open = false;
    this.close();
  }
}

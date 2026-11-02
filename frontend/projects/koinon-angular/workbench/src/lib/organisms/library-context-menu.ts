// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
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
import { CdkMenu, CdkMenuItem } from '@angular/cdk/menu';
import { KoinonIcon } from '../atoms/icon';
import { KoinonTextPipe } from '../foundations/i18n';
import type {
  LibraryAction,
  LibraryContextRequest,
  LibraryMenuAction,
} from '../services/library-context-actions';

@Component({
  selector: 'ffk-library-context-menu',
  imports: [CdkMenu, CdkMenuItem, KoinonIcon, KoinonTextPipe],
  template: `<div
    #menu
    popover="manual"
    tabindex="-1"
    class="library-menu"
    cdkMenu
    [attr.aria-label]="'Library actions' | ffkText"
    (keydown.escape)="escape($event)"
    (keydown.tab)="dismissed.emit(true)"
  >
    @for (action of actions; track action.id) {
      <button cdkMenuItem (cdkMenuItemTriggered)="chosen.emit(action.id)">
        <ffk-icon [name]="action.icon" />{{ action.label | ffkText }}
      </button>
    }
  </div>`,
  styleUrl: './library-context-menu.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonLibraryContextMenu implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ required: true }) request!: LibraryContextRequest;
  @Input() actions: LibraryMenuAction[] = [];
  @Output() chosen = new EventEmitter<LibraryAction>();
  @Output() dismissed = new EventEmitter<boolean>();
  @ViewChild('menu', { static: true }) private menu!: ElementRef<HTMLElement>;
  private readonly outside = (event: Event) => {
    if (!event.composedPath().includes(this.menu.nativeElement)) this.dismissed.emit(false);
  };
  private readonly resize = () => this.dismissed.emit(true);
  private ready = false;
  ngOnChanges() {
    if (this.ready)
      queueMicrotask(() => {
        if (this.ready) this.position();
      });
  }
  ngAfterViewInit() {
    const menu = this.menu.nativeElement;
    menu.showPopover?.();
    this.ready = true;
    this.position();
    menu.ownerDocument.addEventListener('pointerdown', this.outside, true);
    menu.ownerDocument.defaultView?.addEventListener('resize', this.resize);
  }
  private position() {
    const menu = this.menu.nativeElement;
    const window = menu.ownerDocument.defaultView;
    const rect = menu.getBoundingClientRect();
    menu.style.left =
      Math.max(8, Math.min(this.request.x, (window?.innerWidth ?? 1024) - rect.width - 8)) + 'px';
    menu.style.top =
      Math.max(8, Math.min(this.request.y, (window?.innerHeight ?? 768) - rect.height - 8)) + 'px';
    menu.querySelector<HTMLElement>('[role=menuitem]')?.focus();
  }
  escape(event: Event) {
    event.preventDefault();
    event.stopPropagation();
    this.dismissed.emit(true);
  }
  ngOnDestroy() {
    this.ready = false;
    const menu = this.menu.nativeElement;
    menu.ownerDocument.removeEventListener('pointerdown', this.outside, true);
    menu.ownerDocument.defaultView?.removeEventListener('resize', this.resize);
    if (menu.hidePopover && menu.matches(':popover-open')) menu.hidePopover();
  }
}

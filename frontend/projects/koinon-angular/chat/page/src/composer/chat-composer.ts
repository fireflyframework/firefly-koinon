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
  TemplateRef,
  ViewChild,
  ViewContainerRef,
  Injector,
  afterNextRender,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CdkMenu, CdkMenuItem } from '@angular/cdk/menu';
import { Overlay, type OverlayRef } from '@angular/cdk/overlay';
import { TemplatePortal } from '@angular/cdk/portal';
import { KoinonIcon, KoinonTextPipe } from '@fireflyframework/koinon-angular';
import type { ComposerAttachment } from './composer-models';
let composerId = 0;
@Component({
  selector: 'ffk-chat-composer',
  imports: [FormsModule, CdkMenu, CdkMenuItem, KoinonIcon, KoinonTextPipe],
  templateUrl: './chat-composer.html',
  styleUrl: './chat-composer.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonChatComposer implements AfterViewInit, OnChanges, OnDestroy {
  @Input() assistantName = 'koinon';
  @Input() value = '';
  @Input() canSend = false;
  @Input() disabled = false;
  @Input() busy = false;
  @Input() running = false;
  @Input() sendLabel = 'Send';
  @Input() attachmentsEnabled = false;
  @Input() attachmentsUnavailableReason = 'File uploads are not enabled in this workspace.';
  @Input() accept = '';
  @Input() attachments: readonly ComposerAttachment[] = [];
  @Input() locale = 'en-US';
  @Input() hint = '';
  @Input() canChooseKnowledge = false;
  @Input() canAddKnowledge = false;
  @Output() valueChange = new EventEmitter<string>();
  @Output() filesSelected = new EventEmitter<File[]>();
  @Output() attachmentRemoved = new EventEmitter<string>();
  @Output() attachmentRetried = new EventEmitter<string>();
  @Output() libraryRequested = new EventEmitter<void>();
  @Output() addKnowledgeRequested = new EventEmitter<void>();
  @Output() sendRequested = new EventEmitter<void>();
  @Output() stopRequested = new EventEmitter<void>();
  @ViewChild('editor') private editor?: ElementRef<HTMLTextAreaElement>;
  @ViewChild('filePicker') private filePicker?: ElementRef<HTMLInputElement>;
  @ViewChild('addTrigger') private addTrigger?: ElementRef<HTMLButtonElement>;
  @ViewChild('addMenu') private addMenu!: TemplateRef<unknown>;
  private readonly overlay = inject(Overlay);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly views = inject(ViewContainerRef);
  private readonly injector = inject(Injector);
  private menu?: OverlayRef;
  private dragDepth = 0;
  readonly dragging = signal(false);
  readonly menuOpen = signal(false);
  readonly failedPreviews = signal(new Set<string>());
  readonly inputId = 'ffk-composer-' + ++composerId;
  ngAfterViewInit() {
    this.resize();
  }
  ngOnChanges() {
    if (this.disabled || this.busy) {
      this.closeMenu(false);
      this.dragDepth = 0;
      this.dragging.set(false);
    }
    const current = new Set(this.attachments.map((item) => item.id + ':' + item.previewUrl));
    this.failedPreviews.update((keys) => new Set([...keys].filter((key) => current.has(key))));
    afterNextRender(() => this.resize(), { injector: this.injector });
  }
  ngOnDestroy() {
    this.closeMenu(false);
  }
  private resize() {
    const input = this.editor?.nativeElement;
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = Math.min(180, Math.max(32, input.scrollHeight)) + 'px';
  }
  updateValue(value: string) {
    this.value = value;
    this.valueChange.emit(value);
    this.resize();
  }
  keydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && this.readyToSend) {
      event.preventDefault();
      this.sendRequested.emit();
    }
  }
  get readyToSend() {
    return (
      this.canSend &&
      !this.disabled &&
      !this.busy &&
      !this.running &&
      this.attachments.every((item) => item.state === 'ready')
    );
  }
  submit() {
    if (this.readyToSend) this.sendRequested.emit();
  }
  selectFiles(event: Event) {
    const input = event.target as HTMLInputElement;
    if (this.attachmentsEnabled && !this.disabled && !this.busy && input.files?.length)
      this.filesSelected.emit(Array.from(input.files));
    input.value = '';
  }
  paste(event: ClipboardEvent) {
    if (
      !this.attachmentsEnabled ||
      this.disabled ||
      this.busy ||
      !event.clipboardData?.files.length
    )
      return;
    event.preventDefault();
    this.filesSelected.emit(Array.from(event.clipboardData.files));
  }
  dragEnter(event: DragEvent) {
    if (
      !this.attachmentsEnabled ||
      this.disabled ||
      this.busy ||
      !Array.from(event.dataTransfer?.types ?? []).includes('Files')
    )
      return;
    event.preventDefault();
    ++this.dragDepth;
    this.dragging.set(true);
  }
  dragOver(event: DragEvent) {
    if (this.dragging()) {
      event.preventDefault();
      if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
    }
  }
  dragLeave(event: DragEvent) {
    if (this.dragging()) {
      event.preventDefault();
      if (--this.dragDepth <= 0) this.dragging.set(false);
    }
  }
  drop(event: DragEvent) {
    if (!this.attachmentsEnabled || this.disabled || this.busy || !event.dataTransfer?.files.length)
      return;
    event.preventDefault();
    event.stopPropagation();
    this.dragDepth = 0;
    this.dragging.set(false);
    this.filesSelected.emit(Array.from(event.dataTransfer.files));
  }
  toggleMenu() {
    if (this.menu) {
      this.closeMenu();
      return;
    }
    if (!this.addTrigger || this.disabled || this.busy) return;
    const position = this.overlay
      .position()
      .flexibleConnectedTo(this.addTrigger.nativeElement)
      .withViewportMargin(12)
      .withPush(true)
      .withPositions([
        { originX: 'start', originY: 'top', overlayX: 'start', overlayY: 'bottom', offsetY: -8 },
        { originX: 'start', originY: 'bottom', overlayX: 'start', overlayY: 'top', offsetY: 8 },
      ]);
    const menu = this.overlay.create({
      positionStrategy: position,
      scrollStrategy: this.overlay.scrollStrategies.reposition(),
      hasBackdrop: false,
    });
    const tokens = getComputedStyle(this.host.nativeElement);
    for (const token of [
      '--ui-surface',
      '--ui-canvas',
      '--ui-subtle',
      '--ui-text',
      '--ui-muted',
      '--ui-line',
      '--ui-accent',
      '--ui-action',
      '--ui-action-text',
      '--ui-focus',
      '--ffk-font',
    ]) {
      const value = tokens.getPropertyValue(token).trim();
      if (value) menu.overlayElement.style.setProperty(token, value);
    }
    this.menu = menu;
    this.menuOpen.set(true);
    menu.attach(new TemplatePortal(this.addMenu, this.views));
    menu.outsidePointerEvents().subscribe((event) => {
      const trigger = this.addTrigger?.nativeElement;
      if (!trigger || !event.composedPath().includes(trigger)) this.closeMenu(false);
    });
    menu.keydownEvents().subscribe((event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        this.closeMenu();
      }
      if (event.key === 'Tab') this.closeMenu();
    });
    queueMicrotask(() => {
      if (this.menu === menu)
        (
          menu.overlayElement.querySelector<HTMLElement>('[role=menuitem]:not([disabled])') ??
          menu.overlayElement.querySelector<HTMLElement>('[role=menu]')
        )?.focus();
    });
  }
  closeMenu(restore = true) {
    this.menu?.dispose();
    this.menu = undefined;
    this.menuOpen.set(false);
    if (restore) this.addTrigger?.nativeElement.focus();
  }
  pickFiles() {
    this.closeMenu();
    if (this.disabled || this.busy || !this.attachmentsEnabled) return;
    this.filePicker?.nativeElement.click();
  }
  chooseKnowledge() {
    this.closeMenu();
    if (this.disabled || this.busy || !this.canChooseKnowledge) return;
    this.libraryRequested.emit();
  }
  addKnowledge() {
    this.closeMenu();
    if (this.disabled || this.busy || !this.canAddKnowledge) return;
    this.addKnowledgeRequested.emit();
  }
  previewFailed(item: ComposerAttachment) {
    this.failedPreviews.update((keys) => new Set([...keys, item.id + ':' + item.previewUrl]));
  }
  progress(item: ComposerAttachment): number | null {
    return typeof item.progress === 'number' && Number.isFinite(item.progress)
      ? Math.min(100, Math.max(0, item.progress))
      : null;
  }
  status(item: ComposerAttachment) {
    return {
      selected: 'Waiting to upload',
      uploading: 'Uploading',
      processing: 'Reading file',
      ready: 'Ready',
      failed: 'Needs attention',
    }[item.state];
  }
  size(bytes: number) {
    if (bytes < 1024) return bytes + ' B';
    return (
      new Intl.NumberFormat(this.locale, { maximumFractionDigits: 1 }).format(
        bytes / (bytes < 1048576 ? 1024 : 1048576),
      ) + (bytes < 1048576 ? ' KB' : ' MB')
    );
  }
}

// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
import { KoinonTextPipe } from '../foundations/i18n';
import {
  Component,
  Input,
  Output,
  EventEmitter,
  ChangeDetectionStrategy,
  signal,
  HostListener,
  ViewChild,
  ElementRef,
  AfterViewInit,
  OnDestroy,
  inject,
} from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { KoinonAccountMenu } from './account-menu';
import { KoinonIcon } from '../atoms/icon';
import { KoinonSearchField } from '../molecules/search-field';
export type PrimaryDestination = 'library' | 'chat' | 'activity' | 'settings';
export interface OrganizationOption {
  id: string;
  name: string;
}
@Component({
  selector: 'ffk-shell',
  imports: [
    KoinonTextPipe,
    CdkTrapFocus,
    KoinonAccountMenu,
    KoinonIcon,
    KoinonSearchField,
  ],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonShell implements AfterViewInit, OnDestroy {
  @Input() personalAccount = false;
  @Input() destination: PrimaryDestination = 'library';
  @Input() theme: 'light' | 'dark' = 'light';
  @Input() showNavigation = true;
  @Input() productName = 'koinon';
  @Input() brandLogo?: string;
  logo(){return this.brandLogo ?? (this.brandBase+'/logos/firefly-koinon-lockup-'+(this.theme==='dark'?'reversed':'color')+'.svg');}
  @Input() brandBase = '/assets/brand';
  @Input() organizations: OrganizationOption[] = [];
  @Input() tenantId = '';
  @Input() displayName = '';
  @Input() avatarUrl = '';
  @Input() roleLabel = 'Member';
  @Input() canConfigure = false;
  @Input() search = '';
  @Output() destinationChanged = new EventEmitter<PrimaryDestination>();
  @Output() organizationChanged = new EventEmitter<string>();
  @Output() searchChanged = new EventEmitter<string>();
  @Output() searchSubmitted = new EventEmitter<string>();
  @Output() themeChanged = new EventEmitter<'light' | 'dark'>();
  @Output() accountRequested = new EventEmitter<'profile' | 'tokens' | 'applications'>();
  @Output() signOut = new EventEmitter<void>();
  @Output() commandsRequested = new EventEmitter<void>();
  @ViewChild('menuButton') private menuButton?: ElementRef<HTMLButtonElement>;
  @ViewChild('avatarButton') private avatarButton?: ElementRef<HTMLButtonElement>;
  @ViewChild('accountMenu') private accountMenu?: ElementRef<HTMLElement>;
  @HostListener('keydown.escape') closeMenu() {
    if (this.accountMenuOpen()) {
      this.closeAccountMenu();
      return;
    }
    const wasOpen = this.menuOpen();
    this.menuOpen.set(false);
    if (wasOpen) this.menuButton?.nativeElement.focus();
  }
  @ViewChild('content') private content?: ElementRef<HTMLElement>;
  focusContent(event: Event) {
    event.preventDefault();
    this.content?.nativeElement.focus();
  }
  readonly menuOpen = signal(false);
  readonly accountMenuOpen = signal(false);
  readonly compact = signal(true);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  private observer?: ResizeObserver;
  ngAfterViewInit() {
    const resize = (width: number) => {
      this.compact.set(width <= 1100);
      if (width > 1100) this.menuOpen.set(false);
    };
    resize(this.host.nativeElement.getBoundingClientRect().width);
    if (typeof ResizeObserver !== 'undefined') {
      this.observer = new ResizeObserver((entries) => resize(entries[0].contentRect.width));
      this.observer.observe(this.host.nativeElement);
    }
  }
  ngOnDestroy() {
    this.observer?.disconnect();
  }
  toggleNavigation() {
    this.closeAccountMenu(false);
    this.menuOpen.set(!this.menuOpen());
  }
  @HostListener('document:pointerdown', ['$event']) outside(event: PointerEvent) {
    const path = event.composedPath();
    if (
      this.accountMenuOpen() &&
      !path.includes(this.accountMenu?.nativeElement as EventTarget) &&
      !path.includes(this.avatarButton?.nativeElement as EventTarget)
    )
      this.closeAccountMenu(false);
  }
  toggleAccountMenu() {
    if (this.accountMenuOpen()) {
      this.closeAccountMenu();
      return;
    }
    this.menuOpen.set(false);
    this.accountMenuOpen.set(true);
    queueMicrotask(() =>
      this.accountMenu?.nativeElement.querySelector<HTMLElement>('[role=menuitem]')?.focus(),
    );
  }
  closeAccountMenu(restore = true) {
    const open = this.accountMenuOpen();
    this.accountMenuOpen.set(false);
    if (open && restore) this.avatarButton?.nativeElement.focus();
  }
  accountKey(event: KeyboardEvent) {
    if (event.key === 'Tab') this.closeAccountMenu();
  }
  requestSignOut() {
    this.closeAccountMenu();
    this.menuOpen.set(false);
    this.signOut.emit();
  }
  switchTheme() {
    this.themeChanged.emit(this.theme === 'light' ? 'dark' : 'light');
  }
  readonly failedAvatar = signal('');
  readonly destinations: { id: PrimaryDestination; label: string; icon: string }[] = [
    { id: 'library', label: 'Library', icon: 'folder' },
    { id: 'chat', label: 'Chat', icon: 'chat' },
    { id: 'activity', label: 'Activity', icon: 'history' },
  ];
  go(destination: PrimaryDestination, event?: Event) {
    event?.preventDefault();
    this.closeAccountMenu(false);
    this.menuOpen.set(false);
    this.destinationChanged.emit(destination);
  }
  requestAccount(kind: 'profile' | 'tokens' | 'applications') {
    this.closeAccountMenu();
    this.closeMenu();
    this.accountRequested.emit(kind);
  }
  organizationName() {
    return this.organizations.find((x) => x.id === this.tenantId)?.name || 'Choose organization';
  }
  initials() {
    return (this.displayName || 'Your account')
      .split(/[@.\s]/)
      .filter(Boolean)
      .slice(0, 2)
      .map((x) => Array.from(x)[0])
      .join('')
      .toUpperCase();
  }
}

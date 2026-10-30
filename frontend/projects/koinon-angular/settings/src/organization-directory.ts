// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
import {
  ChangeDetectionStrategy,
  ElementRef,
  computed,
  afterNextRender,
  Injector,
  Component,
  PendingTasks,
  effect,
  untracked,
  inject,
  signal,
} from '@angular/core';
import type { OrganizationPerson } from '@fireflyframework/koinon-sdk';
import { FormsModule } from '@angular/forms';
import {
  KoinonButton,
  KoinonTextPipe,
  KoinonPagination,
  KoinonIcon,
} from '@fireflyframework/koinon-angular';
import { KoinonOrganizationDirectory } from '@fireflyframework/koinon-angular/workbench';
import { KoinonOrganizationPosition } from './organization-position';
import { KoinonOrganizationGovernance } from './organization-governance';
import { registerKoinonSpanish } from '@fireflyframework/koinon-angular/workbench';
import { ORGANIZATION_SPANISH } from './organization-spanish';
registerKoinonSpanish(ORGANIZATION_SPANISH);
@Component({
  selector: 'ffk-organization-directory',
  imports: [
    FormsModule,
    KoinonButton,
    KoinonTextPipe,
    KoinonPagination,
    KoinonIcon,
    KoinonOrganizationPosition,
    KoinonOrganizationGovernance,
  ],
  providers: [KoinonOrganizationDirectory],
  templateUrl: './organization-directory.html',
  styleUrl: './organization-directory.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class KoinonOrganizationPeople {
  readonly s = inject(KoinonOrganizationDirectory);
  private readonly tasks = inject(PendingTasks);
  readonly filters = signal({ q: '', job_title: '', unassigned: false });
  readonly applied = signal({ q: '', job_title: '', unassigned: false });
  readonly filtersOpen = signal(false);
  readonly activeFilterCount = computed(() => Object.values(this.applied()).filter(Boolean).length);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly editing = signal(false);
  private readonly injector = inject(Injector);
  private editTrigger: HTMLElement | null = null;
  readonly governance = signal(false);
  constructor() {
    effect(() => {
      this.s.contextIdentity();
      untracked(() => {
        this.filtersOpen.set(false);
        this.editing.set(false);
        this.governance.set(false);
        this.filters.set({ q: '', job_title: '', unassigned: false });
        this.applied.set(this.filters());
        if (!this.s.denied()) this.tasks.run(() => this.load());
      });
    });
  }
  toggleFilters() {
    if (this.filtersOpen()) this.closeFilters();
    else this.filtersOpen.set(true);
  }
  closeFilters(event?: Event) {
    event?.preventDefault();
    event?.stopPropagation();
    this.filtersOpen.set(false);
    this.focusFilterControl();
  }
  private focusFilterControl() {
    afterNextRender(
      () => {
        const button = this.host.nativeElement.querySelector<HTMLButtonElement>(
          '.people-filter-toggle button',
        );
        if (button?.getClientRects().length) button.focus();
      },
      { injector: this.injector },
    );
  }
  begin(person: OrganizationPerson, event: Event) {
    this.editTrigger = event.currentTarget as HTMLElement;
    void this.s.selectPerson(person);
    this.editing.set(true);
  }
  close() {
    this.editing.set(false);
    afterNextRender(
      () => {
        if (this.editTrigger?.isConnected) this.editTrigger.focus();
      },
      { injector: this.injector },
    );
  }
  load(page = 1) {
    return this.s.loadPeople({
      ...this.applied(),
      unassigned: this.applied().unassigned || undefined,
      page,
    });
  }
  apply() {
    this.closeFilters();
    this.applied.set({ ...this.filters() });
    this.editing.set(false);
    return this.load();
  }
  clear() {
    this.filters.set({ q: '', job_title: '', unassigned: false });
    return this.apply();
  }
  changeFilter(key: 'q' | 'job_title', value: string) {
    this.filters.update((old) => ({ ...old, [key]: value }));
  }
  distinctUnit(person: OrganizationPerson) {
    return (
      !!person.unit &&
      !!person.department &&
      person.unit.id !== person.department.id &&
      person.unit.name.trim().toLowerCase() !== person.department.name.trim().toLowerCase()
    );
  }
  initials(name: string) {
    return (
      name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0])
        .join('')
        .toUpperCase() || '?'
    );
  }
}
